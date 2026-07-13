import { describe, it, expect, vi } from "vitest";
import { Workflow } from "../src/Workflow";
import { Task } from "../src/Task";

describe("React PyWorkflow Library Core", () => {
  it("should run a sequential workflow successfully", async () => {
    const workflow = new Workflow("Sequential Test");
    let ranA = false;
    let ranB = false;

    const taskA = new Task({
      name: "A",
      fn: () => {
        ranA = true;
        return "resultA";
      },
    });

    const taskB = new Task({
      name: "B",
      dependsOn: ["A"],
      fn: (ctx) => {
        ranB = true;
        expect(ctx["A"]).toBe("resultA");
        return "resultB";
      },
    });

    workflow.addTask(taskA).addTask(taskB);
    const report = await workflow.run();

    expect(report.success).toBe(true);
    expect(ranA).toBe(true);
    expect(ranB).toBe(true);
    expect(report.results["A"]).toBe("resultA");
    expect(report.results["B"]).toBe("resultB");
    expect(workflow.state).toBe("COMPLETED");
  });

  it("should run independent tasks concurrently in parallel mode", async () => {
    const workflow = new Workflow("Parallel Test");
    const executionOrder: string[] = [];

    const taskA = new Task({
      name: "A",
      fn: async () => {
        await new Promise((r) => setTimeout(r, 50));
        executionOrder.push("A");
        return "A";
      },
    });

    const taskB = new Task({
      name: "B",
      fn: async () => {
        await new Promise((r) => setTimeout(r, 10));
        executionOrder.push("B");
        return "B";
      },
    });

    const taskC = new Task({
      name: "C",
      dependsOn: ["A", "B"],
      fn: () => {
        executionOrder.push("C");
        return "C";
      },
    });

    workflow.addTask(taskA).addTask(taskB).addTask(taskC);
    const report = await workflow.run({ parallel: true });

    expect(report.success).toBe(true);
    // B finishes before A, but both must finish before C
    expect(executionOrder[0]).toBe("B");
    expect(executionOrder[1]).toBe("A");
    expect(executionOrder[2]).toBe("C");
  });

  it("should handle conditional tasks and skip them if condition returns false", async () => {
    const workflow = new Workflow("Condition Test");
    let ranB = false;

    const taskA = new Task({
      name: "A",
      fn: () => ({ shouldRunB: false }),
    });

    const taskB = new Task({
      name: "B",
      dependsOn: ["A"],
      condition: (ctx) => ctx["A"].shouldRunB === true,
      fn: () => {
        ranB = true;
      },
    });

    workflow.addTask(taskA).addTask(taskB);
    const report = await workflow.run();

    expect(report.success).toBe(true);
    expect(ranB).toBe(false);
    expect(taskB.state).toBe("SKIPPED");
    expect(report.skippedTasks).toContain("B");
  });

  it("should handle retries on failure before succeeding", async () => {
    const workflow = new Workflow("Retry Test");
    let attempts = 0;

    const taskA = new Task({
      name: "A",
      retries: 2,
      retryDelay: 5,
      fn: () => {
        attempts++;
        if (attempts < 3) {
          throw new Error("Temporary failure");
        }
        return "success";
      },
    });

    workflow.addTask(taskA);
    const report = await workflow.run();

    expect(report.success).toBe(true);
    expect(attempts).toBe(3);
    expect(taskA.state).toBe("COMPLETED");
  });

  it("should fail workflow and stop downstream if continueOnFailure is false", async () => {
    const workflow = new Workflow("Failure Test");
    let ranB = false;

    const taskA = new Task({
      name: "A",
      fn: () => {
        throw new Error("Fatal task A failure");
      },
    });

    const taskB = new Task({
      name: "B",
      dependsOn: ["A"],
      fn: () => {
        ranB = true;
      },
    });

    workflow.addTask(taskA).addTask(taskB);
    const report = await workflow.run();

    expect(report.success).toBe(false);
    expect(ranB).toBe(false);
    expect(taskB.state).toBe("PENDING");
    expect(report.failedTasks).toContain("A");
    expect(report.skippedTasks).not.toContain("B");
  });

  it("should validate missing dependency configuration", () => {
    const workflow = new Workflow("Missing Dep Test");
    const taskA = new Task({
      name: "A",
      dependsOn: ["NonExistentTask"],
      fn: () => {},
    });

    workflow.addTask(taskA);
    expect(() => workflow.validate()).toThrow(/depends on missing task/);
  });

  it("should validate cyclic dependency configurations", () => {
    const workflow = new Workflow("Cycle Test");
    const taskA = new Task({
      name: "A",
      dependsOn: ["B"],
      fn: () => {},
    });
    const taskB = new Task({
      name: "B",
      dependsOn: ["A"],
      fn: () => {},
    });

    workflow.addTask(taskA).addTask(taskB);
    expect(() => workflow.validate()).toThrow(/contains a cyclic dependency/);
  });
});
