export type TaskState =
  | "PENDING"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED"
  | "RETRYING"
  | "CANCELLED";

export type WorkflowState =
  | "CREATED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "PAUSED";

export interface TaskResult<T = any> {
  state: TaskState;
  output?: T;
  error?: string;
  exception?: Error;
  startedAt?: number;
  finishedAt?: number;
  attempt: number;
}

export interface ExecutionReport {
  success: boolean; // Wait, in TS/JS it is `boolean`, let's make sure it's boolean
  results: Record<string, any>;
  error?: Error;
  failedTasks: string[];
  skippedTasks: string[];
}

export interface TaskOptions<T = any> {
  name: string;
  fn: (context: Record<string, any>) => Promise<T> | T;
  description?: string;
  retries?: number;
  retryDelay?: number; // in ms
  timeout?: number; // in ms
  dependsOn?: string[];
  condition?: (context: Record<string, any>) => boolean | Promise<boolean>;
  onFailure?: (taskName: string, error: Error) => void | Promise<void>;
  continueOnFailure?: boolean;
}
