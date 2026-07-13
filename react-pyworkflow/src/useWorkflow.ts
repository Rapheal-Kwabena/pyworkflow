import { useState, useEffect, useCallback, useRef } from "react";
import { Workflow } from "./Workflow";
import { WorkflowState, TaskState, ExecutionReport } from "./types";

export function useWorkflow(workflow: Workflow) {
  const [workflowState, setWorkflowState] = useState<WorkflowState>(workflow.state);
  const [taskStates, setTaskStates] = useState<Record<string, TaskState>>(() => {
    const initialStates: Record<string, TaskState> = {};
    workflow.tasks.forEach((task, name) => {
      initialStates[name] = task.state;
    });
    return initialStates;
  });

  const [outputs, setOutputs] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Keep a mutable ref to workflow for stable execution callback
  const workflowRef = useRef(workflow);
  useEffect(() => {
    workflowRef.current = workflow;
  }, [workflow]);

  // Synchronize state helpers
  const syncState = useCallback(() => {
    const wf = workflowRef.current;
    setWorkflowState(wf.state);

    const nextTaskStates: Record<string, TaskState> = {};
    const nextOutputs: Record<string, any> = {};
    const nextErrors: Record<string, string> = {};

    wf.tasks.forEach((task, name) => {
      nextTaskStates[name] = task.state;
      if (task.output !== undefined) nextOutputs[name] = task.output;
      if (task.error !== undefined) nextErrors[name] = task.error;
    });

    setTaskStates(nextTaskStates);
    setOutputs(nextOutputs);
    setErrors(nextErrors);
  }, []);

  useEffect(() => {
    const wf = workflow;
    // Initial sync
    syncState();

    const unsubscribeWf = wf.onStateChange((state) => {
      setWorkflowState(state);
    });

    const unsubscribeTasks = wf.onTaskStateChange((taskName, state) => {
      setTaskStates((prev) => ({ ...prev, [taskName]: state }));

      const task = wf.tasks.get(taskName);
      if (task) {
        if (task.output !== undefined) {
          setOutputs((prev) => ({ ...prev, [taskName]: task.output }));
        }
        if (task.error !== undefined) {
          setErrors((prev) => ({ ...prev, [taskName]: task.error! }));
        }
      }
    });

    return () => {
      unsubscribeWf();
      unsubscribeTasks();
    };
  }, [workflow, syncState]);

  const run = useCallback(
    async (options?: { parallel?: boolean }): Promise<ExecutionReport> => {
      const report = await workflowRef.current.run(options);
      syncState();
      return report;
    },
    [syncState]
  );

  const reset = useCallback(() => {
    workflowRef.current.reset();
    syncState();
  }, [syncState]);

  return {
    state: workflowState,
    taskStates,
    outputs,
    errors,
    isRunning: workflowState === "RUNNING",
    run,
    reset,
  };
}
