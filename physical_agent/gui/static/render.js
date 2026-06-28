function createGuiRenderer({ els, t, setLastState, setLastIntegrationResult, updateIntegrationStepState }) {
let timelineFilter = "all";

function escapeHtml(text) {
      return String(text).replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      }[char]));
    }

function item(title, body) {
      const div = document.createElement("div");
      div.className = "item";
      div.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(body || "")}</span>`;
      return div;
    }

function compactJson(value) {
      if (value === undefined || value === null) return "";
      if (Array.isArray(value) && value.length === 0) return "";
      if (typeof value === "object" && Object.keys(value).length === 0) return "";
      return JSON.stringify(value);
    }

function kv(label, value) {
      const text = Array.isArray(value) ? value.join(", ") : String(value || "");
      if (!text) return null;
      const row = document.createElement("div");
      row.innerHTML = `<strong>${escapeHtml(label)}:</strong> ${escapeHtml(text)}`;
      return row;
    }

function chipList(values) {
      const list = document.createElement("div");
      list.className = "chip-list";
      for (const value of values.filter(Boolean)) {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = value;
        list.appendChild(chip);
      }
      return list;
    }

function compactPose(pose) {
      if (!pose || typeof pose !== "object") return "";
      return ["x", "y", "z"]
        .filter(axis => pose[axis] !== undefined && pose[axis] !== null)
        .map(axis => `${axis}:${Number(pose[axis]).toFixed(2)}`)
        .join(", ");
    }

function worldCard(title, subtitle, rows, chips = []) {
      const card = document.createElement("div");
      card.className = "world-card";
      const head = document.createElement("div");
      head.className = "world-card-head";
      const titleWrap = document.createElement("div");
      const name = document.createElement("div");
      name.className = "world-card-title";
      name.textContent = title;
      titleWrap.appendChild(name);
      if (subtitle) {
        const sub = document.createElement("div");
        sub.className = "world-card-subtitle";
        sub.textContent = subtitle;
        titleWrap.appendChild(sub);
      }
      head.appendChild(titleWrap);
      card.appendChild(head);

      const details = document.createElement("div");
      details.className = "kv-grid";
      for (const row of rows.filter(Boolean)) details.appendChild(row);
      if (details.children.length > 0) card.appendChild(details);
      if (chips.length > 0) card.appendChild(chipList(chips));
      return card;
    }

function timelineSection(title, rows) {
      const values = rows.filter(Boolean);
      if (!values.length) return null;
      const section = document.createElement("div");
      section.className = "timeline-section";
      const heading = document.createElement("div");
      heading.className = "timeline-section-title";
      heading.textContent = title;
      section.appendChild(heading);
      const details = document.createElement("div");
      details.className = "kv-grid";
      for (const row of values) details.appendChild(row);
      section.appendChild(details);
      return section;
    }

function timelineDetails(title, sections) {
      const values = sections.filter(Boolean);
      if (!values.length) return null;
      const details = document.createElement("details");
      details.className = "timeline-details";
      const summary = document.createElement("summary");
      summary.textContent = title;
      details.appendChild(summary);
      for (const section of values) details.appendChild(section);
      return details;
    }

function actionObjectLabel(action, feedback) {
      const params = action.params || {};
      const result = feedback.result || {};
      return params.object_id || params.target || result.object_id || result.target || "";
    }

function statusPill(status) {
      const span = document.createElement("span");
      span.className = `status-pill ${status || ""}`;
      span.textContent = statusLabel(status);
      return span;
    }

function statusLabel(status) {
      return t(status || "") || status || "";
    }

function listItems(items, fallback, code = false) {
      const values = (items || []).filter(Boolean);
      if (!values.length) return `<ul><li>${escapeHtml(fallback)}</li></ul>`;
      return `<ul>${values.map(value => {
        const text = escapeHtml(value);
        return `<li>${code ? `<code>${text}</code>` : text}</li>`;
      }).join("")}</ul>`;
    }

function renderIntegrationResult(payload) {
      setLastIntegrationResult(payload);
      const result = payload && payload.result ? payload.result : {};
      const outputPath = result.output_path || (result.integration || {}).output_path || "";
      const files = result.generated_files || [];
      const nextSteps = result.next_steps || (result.source || {}).next_steps || [];
      els.integrateResult.style.display = "grid";
      els.integrateResult.innerHTML = `
        <h3>${escapeHtml(t("integrateResultTitle"))}</h3>
        <div class="kv-grid">
          <div><strong>${escapeHtml(t("integrateOutput"))}:</strong> <code>${escapeHtml(outputPath || "")}</code></div>
          <div><strong>${escapeHtml(t("integrateFiles"))}:</strong></div>
        </div>
        ${listItems(files, t("integrateNoFiles"), true)}
        <div class="kv-grid"><div><strong>${escapeHtml(t("integrateNextSteps"))}:</strong></div></div>
        ${listItems(nextSteps, t("integrateNoNextSteps"))}
      `;
      updateIntegrationStepState("review");
      els.integrateResult.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

function render(state) {
      setLastState(state);
      const ready = Boolean(state.ready);
      els.status.className = ready ? "badge ok" : "badge warn";
      els.status.textContent = ready ? (state.watch_started ? t("readyWatch") : t("readyStopped")) : t("setupNeeded");

      renderChat(state);
      renderCodeResult(state);
      renderWorld(state);
      renderTimeline(state);
      renderSystem(state);
    }

function renderCodeResult(state) {
      const codeResult = state.code_result || null;
      if (!codeResult) {
        els.codeResultPanel.style.display = "none";
        els.codeResultJson.textContent = "{}";
        return;
      }
      els.codeResultPanel.style.display = "block";
      els.codeResultJson.textContent = JSON.stringify(codeResult, null, 2);
    }

function renderChat(state) {
      els.chatLog.innerHTML = "";
      const messages = ((state.chat || {}).messages) || [];
      if (messages.length === 0) {
        const empty = document.createElement("div");
        empty.className = "message system";
        empty.textContent = t("noChat");
        els.chatLog.appendChild(empty);
        return;
      }
      for (const message of messages.slice(-16)) {
        const div = document.createElement("div");
        const role = ["user", "assistant", "system"].includes(message.role) ? message.role : "system";
        div.className = `message ${role}`;
        const body = document.createElement("div");
        body.className = "message-body";
        body.textContent = message.content || "";
        div.appendChild(body);
        els.chatLog.appendChild(div);
      }
      els.chatLog.scrollTop = els.chatLog.scrollHeight;
    }

function renderWorld(state) {
      const world = state.world || {};
      const worldState = world.state || {};
      els.worldSummary.textContent = world.summary || t("noWorld");
      els.worldRobots.innerHTML = "";
      els.worldObjects.innerHTML = "";
      const capabilityRobots = ((state.capabilities || {}).robots) || {};
      const observedRobots = worldState.robots || {};
      const robotIds = new Set([...Object.keys(capabilityRobots), ...Object.keys(observedRobots)]);
      if (robotIds.size === 0) {
        els.worldRobots.appendChild(item(t("noRobots"), t("startWatchHint")));
        return;
      }

      const robotHeading = document.createElement("h3");
      robotHeading.className = "world-group-title";
      robotHeading.textContent = t("robotsSection");
      els.worldRobots.appendChild(robotHeading);
      for (const id of robotIds) {
        const capabilityRobot = capabilityRobots[id] || {};
        const observedRobot = observedRobots[id] || {};
        const caps = (capabilityRobot.capabilities || []).map(cap => cap.name);
        els.worldRobots.appendChild(worldCard(
          id,
          [capabilityRobot.kind, capabilityRobot.driver].filter(Boolean).join(" · "),
          [
            kv(t("status"), observedRobot.status || ""),
            kv(t("holding"), observedRobot.holding || t("none")),
            kv(t("pose"), compactPose(observedRobot.pose))
          ],
          caps
        ));
      }

      const objects = worldState.objects || {};
      if (Object.keys(objects).length === 0) {
        els.worldObjects.appendChild(item(t("objectsSection"), t("noObjects")));
        return;
      }
      const objectHeading = document.createElement("h3");
      objectHeading.className = "world-group-title";
      objectHeading.textContent = t("objectsSection");
      els.worldObjects.appendChild(objectHeading);
      for (const [id, object] of Object.entries(objects)) {
        els.worldObjects.appendChild(worldCard(
          id,
          [object.type, object.color].filter(Boolean).join(" · "),
          [
            kv(t("location"), object.location || ""),
            kv(t("pose"), compactPose(object.pose))
          ],
          object.tags || []
        ));
      }
    }

function renderTimeline(state) {
      els.timeline.innerHTML = "";
      const board = state.actions || { pending: [], completed: [], cancelled: [] };
      const feedbackHistory = Array.isArray((state.feedback || {}).history) ? state.feedback.history : [];
      const feedbackByAction = {};
      for (const entry of feedbackHistory) {
        if (entry && entry.action_id) feedbackByAction[entry.action_id] = entry;
      }
      const actionIds = new Set([
        ...((board.pending || []).map(action => action.id)),
        ...((board.completed || []).map(action => action.id)),
        ...((board.cancelled || []).map(action => action.id))
      ].filter(Boolean));
      const rows = [
        ...((board.pending || []).map(action => ({type: "action", ...action, status: "pending"}))),
        ...((board.completed || []).map(action => {
          const feedback = feedbackByAction[action.id] || {};
          return {type: "action", ...action, status: feedback.status || "completed", feedback};
        })),
        ...((board.cancelled || []).map(action => {
          const feedback = feedbackByAction[action.id] || {};
          return {type: "action", ...action, status: feedback.status || "cancelled", feedback};
        })),
        ...feedbackHistory
          .filter(entry => entry && entry.action_id && !actionIds.has(entry.action_id))
          .map(entry => ({type: "feedback", status: entry.status || "", feedback: entry, id: entry.action_id}))
      ];
      if (rows.length === 0) {
        els.timeline.appendChild(item(t("timelineTitle"), t("noTimeline")));
        return;
      }
      const filteredRows = timelineFilter === "all"
        ? rows
        : rows.filter(row => row.status === timelineFilter);
      if (filteredRows.length === 0) {
        els.timeline.appendChild(item(t("timelineTitle"), t("noTimelineForFilter")));
        return;
      }
      const actionNumber = value => {
        const match = String(value || "").match(/(\d+)$/);
        return match ? Number(match[1]) : 0;
      };
      filteredRows.sort((left, right) => actionNumber(left.id) - actionNumber(right.id));
      for (const action of filteredRows.slice(-4).reverse()) {
        const feedback = action.feedback || {};
        const card = document.createElement("div");
        card.className = `timeline-entry ${action.status}`;

        const head = document.createElement("div");
        head.className = "timeline-head";
        const title = document.createElement("div");
        title.className = "timeline-title";
        const objectLabel = actionObjectLabel(action, feedback);
        title.textContent = [
          action.id || "",
          `${action.robot || feedback.robot || ""}.${action.capability || feedback.capability || ""}`,
          objectLabel
        ].filter(Boolean).join(" · ");
        head.appendChild(title);
        head.appendChild(statusPill(action.status));
        card.appendChild(head);

        const failureText = feedback.message || action.reason || "";
        if (["failed", "cancelled"].includes(action.status) && failureText) {
          const alert = document.createElement("div");
          alert.className = "timeline-alert";
          alert.innerHTML = `<strong>${escapeHtml(t("failureReason"))}</strong>${escapeHtml(failureText)}`;
          card.appendChild(alert);
        }

        const details = timelineDetails(t("details"), [
          timelineSection(t("requestSection"), [
          kv(t("params"), compactJson(action.params)),
          kv(t("dependsOn"), action.depends_on || []),
            kv(t("reason"), action.reason || "")
          ]),
          timelineSection(t("feedbackSection"), [
          kv(t("message"), feedback.message || ""),
            kv(t("result"), compactJson(feedback.result))
          ]),
          timelineSection(t("artifactSection"), [
            kv(t("artifacts"), feedback.artifacts || [])
          ])
        ]);
        if (details) card.appendChild(details);
        els.timeline.appendChild(card);
      }
    }

function renderSystem(state) {
      els.project.innerHTML = "";
      els.project.appendChild(item(t("config"), state.config_path || t("notCreated")));
      els.project.appendChild(item(t("workspace"), state.workspace_path || t("notCreated")));
      els.project.appendChild(item(t("message"), state.message || ""));
      els.detailsJson.textContent = JSON.stringify({
        plan: state.plan,
        memory: state.memory,
        doctor: state.doctor
      }, null, 2);
    }

  return {
    render,
    renderIntegrationResult,
    setTimelineFilter(filter) {
      timelineFilter = filter || "all";
    },
  };
}

window.GuiRender = { createGuiRenderer };
