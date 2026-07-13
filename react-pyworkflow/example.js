const { Workflow, Task } = require("./dist/index.js");

console.log("🚀 Initializing react-pyworkflow client-side engine simulation...");

// 1. Create a workflow instance
const workflow = new Workflow("Demo Workflow");

// 2. Define mock tasks with artificial delays
const downloadTask = new Task({
  name: "Download Data",
  fn: async () => {
    console.log("  [Task 1] Downloading raw dataset...");
    await new Promise((resolve) => setTimeout(resolve, 800));
    return { records: [ { id: 1, val: 10 }, { id: 2, val: 20 }, { id: 3, val: 30 } ] };
  }
});

const calculateTask = new Task({
  name: "Calculate Sum",
  dependsOn: ["Download Data"],
  fn: async (context) => {
    console.log("  [Task 2] Processing records...");
    const data = context["Download Data"];
    await new Promise((resolve) => setTimeout(resolve, 500));
    const sum = data.records.reduce((acc, curr) => acc + curr.val, 0);
    return { sum };
  }
});

const reportTask = new Task({
  name: "Generate Report",
  dependsOn: ["Calculate Sum"],
  fn: async (context) => {
    console.log("  [Task 3] Generating final summary report...");
    const result = context["Calculate Sum"];
    return `Final calculation: The sum of elements is ${result.sum}`;
  }
});

// 3. Compose workflow graph
workflow
  .addTask(downloadTask)
  .addTask(calculateTask)
  .addTask(reportTask);

// 4. Run the workflow and log states
console.log(`\nStarting Workflow: "${workflow.name}"`);
console.log("-----------------------------------------");

workflow.onStateChange((state) => {
  console.log(`🚩 Workflow State changed to: ${state}`);
});

workflow.onTaskStateChange((taskName, state) => {
  console.log(`  🔹 Task [${taskName}] changed to: ${state}`);
});

workflow.run()
  .then((report) => {
    console.log("-----------------------------------------");
    console.log(`🏁 Execution finished. Success: ${report.success}`);
    console.log("Results context output map:", report.results);
  })
  .catch((err) => {
    console.error("Workflow failed with error:", err);
  });
