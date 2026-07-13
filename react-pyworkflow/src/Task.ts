import { TaskOptions, TaskState, TaskResult } from "./types";

export class Task<T = any> {
  public name: string;
  public fn: (context: Record<string, any>) => Promise<T> | T;
  public description: string;
  public retries: number;
  public retryDelay: number;
  public timeout?: number;
  public dependsOn: string[];
  public condition?: (context: Record<string, any>) => boolean | Promise<boolean>;
  public onFailure?: (taskName: string, error: Error) => void | Promise<void>;
  public continueOnFailure: boolean;

  public state: TaskState = "PENDING";
  public output?: T;
  public error?: string;
  public history: TaskResult<T>[] = [];
  public startedAt?: number;
  public finishedAt?: number;
  public attempts: number = 0;

  constructor(options: TaskOptions<T>) {
    this.name = options.name;
    this.fn = options.fn;
    this.description = options.description || "";
    this.retries = options.retries || 0;
    this.retryDelay = options.retryDelay || 0;
    this.timeout = options.timeout;
    this.dependsOn = options.dependsOn || [];
    this.condition = options.condition;
    this.onFailure = options.onFailure;
    this.continueOnFailure = options.continueOnFailure || false;
  }

  public reset(): void {
    this.state = "PENDING";
    this.output = undefined;
    this.error = undefined;
    this.history = [];
    this.startedAt = undefined;
    this.finishedAt = undefined;
    this.attempts = 0;
  }

  public async run(context: Record<string, any>): Promise<TaskResult<T>> {
    // Check condition first
    if (this.condition) {
      try {
        const shouldRun = await this.condition(context);
        if (!shouldRun) {
          this.state = "SKIPPED";
          const skippedResult: TaskResult<T> = {
            state: "SKIPPED",
            attempt: 0,
            startedAt: Date.now(),
            finishedAt: Date.now(),
          };
          this.history.push(skippedResult);
          return skippedResult;
        }
      } catch (err: any) {
        this.state = "FAILED";
        const condError = err instanceof Error ? err : new Error(String(err));
        this.error = `Condition error: ${condError.message}`;
        const failedResult: TaskResult<T> = {
          state: "FAILED",
          attempt: 1,
          error: this.error,
          exception: condError,
          startedAt: Date.now(),
          finishedAt: Date.now(),
        };
        this.history.push(failedResult);
        if (this.onFailure) {
          try {
            await this.onFailure(this.name, condError);
          } catch (_) {}
        }
        throw condError;
      }
    }

    const maxAttempts = this.retries + 1;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      this.attempts = attempt;
      this.state = attempt === 1 ? "RUNNING" : "RETRYING";
      const started = Date.now();

      try {
        let taskPromise = Promise.resolve(this.fn(context));

        if (this.timeout && this.timeout > 0) {
          const timeoutPromise = new Promise<never>((_, reject) =>
            setTimeout(() => reject(new Error(`Timeout of ${this.timeout}ms exceeded`)), this.timeout)
          );
          taskPromise = Promise.race([taskPromise, timeoutPromise]);
        }

        const result = await taskPromise;
        const finished = Date.now();

        this.state = "COMPLETED";
        this.output = result;
        this.startedAt = started;
        this.finishedAt = finished;

        const successResult: TaskResult<T> = {
          state: "COMPLETED",
          output: result,
          startedAt: started,
          finishedAt: finished,
          attempt,
        };
        this.history.push(successResult);
        return successResult;
      } catch (err: any) {
        const finished = Date.now();
        const errorMsg = err instanceof Error ? err.message : String(err);
        const exception = err instanceof Error ? err : new Error(errorMsg);

        const attemptResult: TaskResult<T> = {
          state: "FAILED",
          error: errorMsg,
          exception,
          startedAt: started,
          finishedAt: finished,
          attempt,
        };
        this.history.push(attemptResult);

        if (attempt < maxAttempts) {
          if (this.retryDelay > 0) {
            await new Promise((resolve) => setTimeout(resolve, this.retryDelay));
          }
          continue;
        }

        // Exhausted all retries
        this.state = "FAILED";
        this.error = errorMsg;
        this.startedAt = started;
        this.finishedAt = finished;

        if (this.onFailure) {
          try {
            await this.onFailure(this.name, exception);
          } catch (_) {}
        }

        if (!this.continueOnFailure) {
          throw exception;
        }

        return attemptResult;
      }
    }

    throw new Error("Unexpected end of retry loop");
  }
}
