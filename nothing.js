<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Weekly To-Do • 2026</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --text: #e2e8f0;
      --accent: #c084fc;
      --done: #6ee7b7;
      --border: #334155;
    }

    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      padding: 20px 12px 60px;
      line-height: 1.5;
    }

    header {
      text-align: center;
      margin: 0 0 2.5rem;
    }

    h1 {
      font-size: 2.4rem;
      color: var(--accent);
      margin-bottom: 0.4rem;
    }

    .subtitle {
      color: #94a3b8;
      font-size: 1.05rem;
    }

    .week-container {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1.5rem;
      max-width: 1400px;
      margin: 0 auto;
    }

    .day-card {
      background: var(--card);
      border-radius: 12px;
      border: 1px solid var(--border);
      overflow: hidden;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.4);
      transition: transform 0.12s ease;
    }

    .day-card:hover {
      transform: translateY(-4px);
    }

    .day-header {
      background: linear-gradient(90deg, #4c1d95, #7c3aed);
      padding: 14px 18px;
      font-weight: bold;
      font-size: 1.3rem;
      color: white;
    }

    .tasks {
      padding: 1rem 1.2rem 1.4rem;
      min-height: 220px;
    }

    .task {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 0.9rem;
      padding: 8px 10px;
      border-radius: 8px;
      background: rgba(30,41,59,0.6);
      transition: all 0.13s;
    }

    .task:hover {
      background: rgba(51,65,85,0.7);
    }

    input[type="checkbox"] {
      width: 18px;
      height: 18px;
      accent-color: var(--done);
      cursor: pointer;
    }

    .task-text {
      flex: 1;
      word-break: break-word;
    }

    .task.done .task-text {
      text-decoration: line-through;
      color: #94a3b8;
      opacity: 0.85;
    }

    .add-task {
      display: flex;
      gap: 8px;
      margin-top: 1.2rem;
    }

    input[type="text"] {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #0f172a;
      color: var(--text);
      font-size: 1rem;
    }

    button {
      padding: 0 16px;
      background: var(--accent);
      color: #0f172a;
      border: none;
      border-radius: 8px;
      font-weight: bold;
      cursor: pointer;
      transition: all 0.15s;
    }

    button:hover {
      background: #d8b4fe;
      transform: translateY(-1px);
    }

    .clear-btn {
      margin-top: 1.5rem;
      background: #f87171;
      color: white;
      width: 100%;
      padding: 10px;
      font-size: 0.95rem;
    }

    .clear-btn:hover {
      background: #ef4444;
    }

    footer {
      text-align: center;
      margin-top: 3rem;
      color: #64748b;
      font-size: 0.9rem;
    }

    @media (max-width: 500px) {
      .week-container {
        grid-template-columns: 1fr;
      }
      h1 { font-size: 2rem; }
    }
  </style>
</head>
<body>

  <header>
    <h1>Weekly To-Do</h1>
    <div class="subtitle">Plan your week • Everything saved in browser</div>
  </header>

  <div class="week-container" id="week"></div>

  <footer>
    Data is saved only in your browser • Clearing browser data = losing tasks
  </footer>

  <script>
    const days = [
      "Monday", "Tuesday", "Wednesday", "Thursday",
      "Friday", "Saturday", "Sunday"
    ];

    const STORAGE_KEY = "weekly-todo-2026";

    function loadData() {
      try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      } catch {
        return {};
      }
    }

    function saveData(data) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }

    function createDayElement(dayName) {
      const card = document.createElement("div");
      card.className = "day-card";
      
      card.innerHTML = `
        <div class="day-header">${dayName}</div>
        <div class="tasks" data-day="${dayName}"></div>
        <div class="tasks-input-area" style="padding:0 1.2rem 1.2rem;">
          <div class="add-task">
            <input type="text" placeholder="New task..." class="new-task-input">
            <button class="add-btn">Add</button>
          </div>
          <button class="clear-btn">Clear completed</button>
        </div>
      `;

      const tasksContainer = card.querySelector(".tasks");
      const input = card.querySelector(".new-task-input");
      const addBtn = card.querySelector(".add-btn");
      const clearBtn = card.querySelector(".clear-btn");

      // Add task
      function addTask(text) {
        if (!text.trim()) return;
        
        const taskDiv = document.createElement("div");
        taskDiv.className = "task";
        taskDiv.innerHTML = `
          <input type="checkbox">
          <span class="task-text">${text}</span>
        `;

        const checkbox = taskDiv.querySelector("input");
        checkbox.addEventListener("change", () => {
          taskDiv.classList.toggle("done", checkbox.checked);
          save();
        });

        tasksContainer.appendChild(taskDiv);
        input.value = "";
        save();
      }

      addBtn.addEventListener("click", () => addTask(input.value));
      input.addEventListener("keypress", e => {
        if (e.key === "Enter") addTask(input.value);
      });

      // Clear completed
      clearBtn.addEventListener("click", () => {
        [...tasksContainer.children].forEach(task => {
          if (task.querySelector("input:checked")) {
            task.remove();
          }
        });
        save();
      });

      return card;
    }

    function save() {
      const data = {};
      document.querySelectorAll(".tasks").forEach(container => {
        const day = container.dataset.day;
        data[day] = [];
        container.querySelectorAll(".task").forEach(task => {
          const text = task.querySelector(".task-text").textContent;
          const done = task.querySelector("input").checked;
          data[day].push({text, done});
        });
      });
      saveData(data);
    }

    function load() {
      const data = loadData();
      document.querySelectorAll(".tasks").forEach(container => {
        const day = container.dataset.day;
        const tasks = data[day] || [];
        container.innerHTML = "";
        tasks.forEach(t => {
          const taskDiv = document.createElement("div");
          taskDiv.className = "task" + (t.done ? " done" : "");
          taskDiv.innerHTML = `
            <input type="checkbox" ${t.done ? "checked" : ""}>
            <span class="task-text">${t.text}</span>
          `;
          taskDiv.querySelector("input").addEventListener("change", e => {
            taskDiv.classList.toggle("done", e.target.checked);
            save();
          });
          container.appendChild(taskDiv);
        });
      });
    }

    // Initialize
    const container = document.getElementById("week");
    days.forEach(day => {
      container.appendChild(createDayElement(day));
    });

    load();

    // Optional: auto-save when leaving page
    window.addEventListener("beforeunload", save);
  </script>

</body>
</html>
