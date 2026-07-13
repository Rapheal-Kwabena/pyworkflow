import { Task } from "./Task";
import { WorkflowState, ExecutionReport, TaskState } from "./types";

export class Workflow {
  public name: string;
  public tasks: Map<string, Task> = new Map();
  public state: WorkflowState = "CREATED";
  public context: Record<string, any> = {};
  public startedAt?: number;
  public finishedAt?: number;

  // Order of insertion to support fluent .then() chaining
  private insertionOrder: string[] = [];

  // Listeners for real-time reactivity
  private stateChangeListeners: ((state: WorkflowState) => void)[] = [];
  private taskStateChangeListeners: ((taskName: string, state: TaskState) => void)[] = [];

  constructor(name: string) {
    this.name = name;
  }

  public addTask(task: Task): this {
    if (this.tasks.has(task.name)) {
      throw new Error(`Task with name '${task.name}' already exists in workflow '${this.name}'`);
    }
    this.tasks.set(task.name, task);
    this.insertionOrder.push(task.name);
    return this;
  }

  public addTasks(tasks: Task[]): this {
    tasks.forEach((t) => this.addTask(t));
    return this;
  }

  public then(task: Task): this {
    if (this.insertionOrder.length > 0) {
      const lastTaskName = this.insertionOrder[this.insertionOrder.length - 1];
      if (!task.dependsOn.includes(lastTaskName)) {
        task.dependsOn.push(lastTaskName);
      }
    }
    return this.addTask(task);
  }

  public reset(): void {
    this.state = "CREATED";
    this.context = {};
    this.startedAt = undefined;
    this.finishedAt = undefined;
    this.tasks.forEach((t) => t.reset());
    this.notifyStateChange("CREATED");
  }

  // Subscribe to workflow state changes
  public onStateChange(listener: (state: WorkflowState) => void): () => void {
    this.stateChangeListeners.push(listener);
    return () => {
      this.stateChangeListeners = this.stateChangeListeners.filter((l) => l !== listener);
    };
  }

  // Subscribe to task state changes
  public onTaskStateChange(listener: (taskName: string, state: TaskState) => void): () => void {
    this.taskStateChangeListeners.push(listener);
    return () => {
      this.taskStateChangeListeners = this.taskStateChangeListeners.filter((l) => l !== listener);
    };
  }

  private notifyStateChange(state: WorkflowState): void {
    this.state = state;
    this.stateChangeListeners.forEach((l) => l(state));
  }

  private notifyTaskStateChange(taskName: string, state: TaskState): void {
    const task = this.tasks.get(taskName);
    if (task) {
      task.state = state;
    }
    this.taskStateChangeListeners.forEach((l) => l(taskName, state));
  }

  public validate(): void {
    // 1. Check for missing dependencies
    this.tasks.forEach((task) => {
      task.dependsOn.forEach((dep) => {
        if (!this.tasks.has(dep)) {
          throw new Error(
            `Task '${task.name}' depends on missing task '${dep}' in workflow '${this.name}'`
          );
        }
      });
    });

    // 2. Check for cycle by calling topological sort
    this.getTopologicalLevels();
  }

  public getTopologicalLevels(): string[][] {
    const inDegree: Record<string, number> = {};
    const dependents: Record<string, string[]> = {};

    this.tasks.forEach((_, name) => {
      inDegree[name] = 0;
      dependents[name] = [];
    });

    this.tasks.forEach((task, name) => {
      task.dependsOn.forEach((dep) => {
        inDegree[name]++;
        dependents[dep].push(name);
      });
    });

    const levels: string[][] = [];
    let remaining = { ...inDegree };
    let placedCount = 0;

    let current = Object.keys(remaining).filter((n) => remaining[n] === 0);

    // Sort current level by insertion order
    current.sort((a, b) => this.insertionOrder.indexOf(a) - this.insertionOrder.indexOf(b));

    while (current.length > 0) {
      levels.push(current);
      placedCount += current.length;

      const nextLevel: string[] = [];
      current.forEach((node) => {
        delete remaining[node];
        dependents[node].forEach((dep) => {
          remaining[dep]--;
          if (remaining[dep] === 0) {
            nextLevel.push(dep);
          }
        });
      });

      nextLevel.sort((a, b) => this.insertionOrder.indexOf(a) - this.insertionOrder.indexOf(b));
      current = nextLevel;
    }

    if (placedCount !== this.tasks.size) {
      throw new Error(`Workflow '${this.name}' contains a cyclic dependency`);
    }

    return levels;
  }

  public async run(options: { parallel?: boolean } = {}): Promise<ExecutionReport> {
    if (this.state === "RUNNING") {
      throw new Error(`Workflow '${this.name}' is already running`);
    }

    this.validate();
    this.startedAt = Date.now();
    this.notifyStateChange("RUNNING");

    const parallel = options.parallel ?? false;
    const failedTasks: string[] = [];
    const skippedTasks: string[] = [];
    let globalError: Error | undefined = undefined;

    try {
      const levels = this.getTopologicalLevels();

      if (parallel) {
        // Execute level-by-level, running tasks within each level concurrently
        for (const level of levels) {
          // Check if previous levels had non-continuable failures
          if (globalError) break;

          const levelPromises = level.map(async (taskName) => {
            const task = this.tasks.get(taskName)!;

            // Check if any dependencies failed or were skipped
            const depFailedOrSkipped = task.dependsOn.some(
              (dep) => failedTasks.includes(dep) || skippedTasks.includes(dep)
            );

            if (depFailedOrSkipped) {
              skippedTasks.push(taskName);
              this.notifyTaskStateChange(taskName, "SKIPPED");
              return;
            }

            this.notifyTaskStateChange(taskName, "RUNNING");
            try {
              // Wrap running status changes during execution loop
              task.onFailure = (name) => {
                this.notifyTaskStateChange(name, "FAILED");
              };
              const taskResult = await task.run(this.context);
              if (taskResult.state === "COMPLETED") {
                this.context[taskName] = taskResult.output;
                this.notifyTaskStateChange(taskName, "COMPLETED");
              } else if (taskResult.state === "SKIPPED") {
                this.notifyTaskStateChange(taskName, "SKIPPED");
                skippedTasks.push(taskName);
              } else {
                failedTasks.push(taskName);
                this.notifyTaskStateChange(taskName, "FAILED");
              }
            } catch (err: any) {
              failedTasks.push(taskName);
              this.notifyTaskStateChange(taskName, "FAILED");
              if (!task.continueOnFailure) {
                globalError = err instanceof Error ? err : new Error(String(err));
              }
            }
          });

          await Promise.all(levelPromises);
        }
      } else {
        // Execute sequentially node by node in topological levels
        for (const level of levels) {
          if (globalError) break;

          for (const taskName of level) {
            const task = this.tasks.get(taskName)!;

            const depFailedOrSkipped = task.dependsOn.some(
              (dep) => failedTasks.includes(dep) || skippedTasks.includes(dep)
            );

            if (depFailedOrSkipped) {
              skippedTasks.push(taskName);
              this.notifyTaskStateChange(taskName, "SKIPPED");
              continue;
            }

            this.notifyTaskStateChange(taskName, "RUNNING");
            try {
              task.onFailure = (name) => {
                this.notifyTaskStateChange(name, "FAILED");
              };
              const taskResult = await task.run(this.context);
              if (taskResult.state === "COMPLETED") {
                this.context[taskName] = taskResult.output;
                this.notifyTaskStateChange(taskName, "COMPLETED");
              } else if (taskResult.state === "SKIPPED") {
                this.notifyTaskStateChange(taskName, "SKIPPED");
                skippedTasks.push(taskName);
              } else {
                failedTasks.push(taskName);
                this.notifyTaskStateChange(taskName, "FAILED");
              }
            } catch (err: any) {
              failedTasks.push(taskName);
              this.notifyTaskStateChange(taskName, "FAILED");
              if (!task.continueOnFailure) {
                globalError = err instanceof Error ? err : new Error(String(err));
                break;
              }
            }
          }
        }
      }

      this.finishedAt = Date.now();
      const success = failedTasks.length === 0 && !globalError;
      this.notifyStateChange(success ? "COMPLETED" : "FAILED");

      return {
        success,
        results: { ...this.context },
        error: globalError,
        failedTasks,
        skippedTasks,
      };
    } catch (err: any) {
      this.finishedAt = Date.now();
      const mainError = err instanceof Error ? err : new Error(String(err));
      this.notifyStateChange("FAILED");
      return {
        success: false,
        results: { ...this.context },
        error: mainError,
        failedTasks,
        skippedTasks,
      };
    }
  }
}
