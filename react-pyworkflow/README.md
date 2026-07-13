# react-pyworkflow ⚛️

A lightweight, client-side JavaScript/TypeScript workflow automation and orchestration library for React. 

Ported directly from the python version of `pyworkflow`, it lets you define async execution graphs (pipelines), handle complex dependencies, run tasks sequentially or concurrently, execute retries with delays, and track real-time status updates directly within React components.

---

## Installation

```bash
npm install react-pyworkflow
# or
yarn add react-pyworkflow
# or
pnpm add react-pyworkflow
```

---

## Features

- ⚛️ **React Hook Integration**: State triggers auto-re-renders of your React components dynamically during execution.
- ⚡ **Concurrent Execution**: Run independent branches in parallel via `Promise.all` with a single option switch.
- 🔄 **Automatic Retries**: Retries with configurable delays.
- 🛑 **Error and Callback Handling**: Control execution with `continueOnFailure` and `onFailure` hooks.
- 🔀 **Conditional Runs**: Skip tasks dynamically using context-based predicate checks.
- 🛠️ **Full TypeScript Support**: Out of the box ESM and CJS builds with `.d.ts` type declarations.

---

## Quick Start

### 1. Define Workflows and Tasks
Create a workflow graph exactly like PyWorkflow:

```typescript
import { Workflow, Task } from "react-pyworkflow";

// 1. Create a workflow
export const dataPipeline = new Workflow("Data Pipeline");

// 2. Define tasks
const fetchTask = new Task({
  name: "Fetch Data",
  fn: async () => {
    const res = await fetch("https://api.example.com/data");
    return res.json();
  },
  retries: 2,
  retryDelay: 1000, // 1s
});

const filterTask = new Task({
  name: "Filter Data",
  dependsOn: ["Fetch Data"],
  fn: (context) => {
    // Upstream task results are automatically injected into context
    const data = context["Fetch Data"];
    return data.filter((item: any) => item.active);
  },
});

const saveTask = new Task({
  name: "Save Data",
  dependsOn: ["Filter Data"],
  fn: async (context) => {
    const filtered = context["Filter Data"];
    await fetch("https://api.example.com/save", {
      method: "POST",
      body: JSON.stringify(filtered),
    });
    return "Saved Successfully!";
  },
});

// 3. Compose workflow
dataPipeline.addTask(fetchTask).addTask(filterTask).addTask(saveTask);
```

### 2. Connect to React Components
Use the `useWorkflow` hook to bind execution state reactively:

```tsx
import React from "react";
import { useWorkflow } from "react-pyworkflow";
import { dataPipeline } from "./pipeline";

export default function PipelineMonitor() {
  const { state, taskStates, outputs, errors, isRunning, run, reset } = useWorkflow(dataPipeline);

  const handleStart = () => {
    run({ parallel: true }); // Runs independent tasks concurrently
  };

  return (
    <div style={{ padding: "20px", fontFamily: "sans-serif" }}>
      <h2>Workflow: {dataPipeline.name}</h2>
      <p>Status: <strong>{state}</strong></p>

      <div style={{ margin: "20px 0" }}>
        <button onClick={handleStart} disabled={isRunning}>
          Start Pipeline
        </button>
        <button onClick={reset} disabled={isRunning} style={{ marginLeft: "10px" }}>
          Reset
        </button>
      </div>

      <h3>Tasks:</h3>
      <ul>
        {Array.from(dataPipeline.tasks.keys()).map((name) => (
          <li key={name} style={{ margin: "10px 0" }}>
            <strong>{name}</strong>: <span style={{ color: getStatusColor(taskStates[name]) }}>{taskStates[name]}</span>
            {outputs[name] && <pre>{JSON.stringify(outputs[name], null, 2)}</pre>}
            {errors[name] && <p style={{ color: "red" }}>Error: {errors[name]}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function getStatusColor(status: string) {
  switch (status) {
    case "COMPLETED": return "green";
    case "RUNNING":
    case "RETRYING": return "orange";
    case "FAILED": return "red";
    case "SKIPPED": return "blue";
    default: return "gray";
  }
}
```

---

## API Reference

### `Workflow`
- `constructor(name: string)`
- `addTask(task: Task): this` — Add a task to the workflow.
- `addTasks(tasks: Task[]): this` — Add multiple tasks at once.
- `then(task: Task): this` — Add a task that depends on the previously added task.
- `reset(): void` — Reset the workflow and all tasks back to `PENDING`.
- `validate(): void` — Validate dependencies and detect cycles.
- `run(options?: { parallel?: boolean }): Promise<ExecutionReport>` — Run the workflow.

### `Task`
- `constructor(options: TaskOptions)`
- **Options**:
  - `name`: `string` (required, unique)
  - `fn`: `(context) => Promise<any> | any` (required, execution body)
  - `retries`: `number` (optional, default: 0)
  - `retryDelay`: `number` (optional, default: 0ms)
  - `timeout`: `number` (optional, timeout in ms)
  - `dependsOn`: `string[]` (optional, dependency task names)
  - `condition`: `(context) => boolean | Promise<boolean>` (optional)
  - `onFailure`: `(taskName, error) => void` (optional callback)
  - `continueOnFailure`: `boolean` (optional, default: false)

---

## License

MIT © PyWorkflow Contributors
