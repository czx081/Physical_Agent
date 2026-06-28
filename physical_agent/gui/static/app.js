const I18N = window.I18N;
const { api: requestApi, post: postApi } = window.GuiApi;
    const els = {
      status: document.querySelector("#status"),
      setup: document.querySelector("#setup"),
      reset: document.querySelector("#reset"),
      startWatch: document.querySelector("#start-watch"),
      stepWatch: document.querySelector("#step-watch"),
      demo: document.querySelector("#demo"),
      refresh: document.querySelector("#refresh"),
      lastMessage: document.querySelector("#last-message"),
      project: document.querySelector("#project"),
      detailsJson: document.querySelector("#details-json"),
      worldSummary: document.querySelector("#world-summary"),
      worldRobots: document.querySelector("#world-robots"),
      worldObjects: document.querySelector("#world-objects"),
      timeline: document.querySelector("#timeline"),
      timelineFilters: document.querySelectorAll("[data-timeline-filter]"),
      chatLog: document.querySelector("#chat-log"),
      chatInput: document.querySelector("#chat-input"),
      chatPlanner: document.querySelector("#chat-planner"),
      chatAutoStep: document.querySelector("#chat-auto-step"),
      sendChat: document.querySelector("#send-chat"),
      codeResultPanel: document.querySelector("#code-result-panel"),
      codeResultJson: document.querySelector("#code-result-json"),
      integrateStepSource: document.querySelector("#integrate-step-source"),
      integrateStepMode: document.querySelector("#integrate-step-mode"),
      integrateStepReview: document.querySelector("#integrate-step-review"),
      integrateSource: document.querySelector("#integrate-source"),
      integrateName: document.querySelector("#integrate-name"),
      integrateModel: document.querySelector("#integrate-model"),
      integrateMode: document.querySelector("#integrate-mode"),
      integrate: document.querySelector("#integrate"),
      integrateResult: document.querySelector("#integrate-result")
    };

    const savedLang = localStorage.getItem("physical-agent-lang");
    let lang = savedLang || ((navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en");
    let lastState = null;
    let lastIntegrationResult = null;
    const setLastState = value => { lastState = value; };
    const setLastIntegrationResult = value => { lastIntegrationResult = value; };

    function t(key) { return (I18N[lang] || I18N.en)[key] || I18N.en[key] || key; }

    function setIntegrationStep(step) {
      updateIntegrationStepState(step);
      if (step === "source") {
        els.integrateSource.focus();
        return;
      }
      if (step === "mode") {
        els.integrateMode.focus();
        return;
      }
      if (step === "review") {
        if (lastIntegrationResult) {
          els.integrateResult.scrollIntoView({ block: "nearest", behavior: "smooth" });
        } else {
          els.integrate.focus();
        }
      }
    }

    function updateIntegrationStepState(activeStep = null) {
      const sourceReady = Boolean(els.integrateSource.value.trim());
      const resultReady = Boolean(lastIntegrationResult);
      const current = activeStep || (resultReady ? "review" : (sourceReady ? "mode" : "source"));
      const steps = {
        source: els.integrateStepSource,
        mode: els.integrateStepMode,
        review: els.integrateStepReview
      };
      for (const [name, node] of Object.entries(steps)) {
        node.classList.toggle("active", name === current);
        node.classList.toggle(
          "done",
          (name === "source" && sourceReady) || (name === "mode" && sourceReady) || (name === "review" && resultReady)
        );
      }
    }

    const renderer = window.GuiRender.createGuiRenderer({
      els,
      t,
      setLastState,
      setLastIntegrationResult,
      updateIntegrationStepState
    });
    const { render, renderIntegrationResult } = renderer;

    function setTimelineFilter(filter) {
      renderer.setTimelineFilter(filter);
      els.timelineFilters.forEach(node => node.classList.toggle("active", node.dataset.timelineFilter === filter));
      if (lastState) render(lastState);
    }

    function setLanguage(next) {
      lang = next;
      localStorage.setItem("physical-agent-lang", lang);
      document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
      const zhButton = document.querySelector('[data-lang="zh"]');
      if (zhButton) zhButton.textContent = "中文";
      document.querySelectorAll("[data-i18n]").forEach(node => { node.textContent = t(node.dataset.i18n); });
      document.querySelectorAll("[data-i18n-placeholder]").forEach(node => { node.placeholder = t(node.dataset.i18nPlaceholder); });
      document.querySelectorAll("[data-lang]").forEach(node => node.classList.toggle("active", node.dataset.lang === lang));
      if (lastState) render(lastState);
      if (lastIntegrationResult) renderIntegrationResult(lastIntegrationResult);
    }

    document.querySelectorAll("[data-lang]").forEach(node => {
      node.addEventListener("click", () => setLanguage(node.dataset.lang));
    });
    els.timelineFilters.forEach(node => {
      node.addEventListener("click", () => setTimelineFilter(node.dataset.timelineFilter));
    });
    els.chatInput.addEventListener("input", () => { els.chatInput.dataset.touched = "true"; });
    els.integrateStepSource.addEventListener("click", () => setIntegrationStep("source"));
    els.integrateStepMode.addEventListener("click", () => setIntegrationStep("mode"));
    els.integrateStepReview.addEventListener("click", () => setIntegrationStep("review"));
    els.integrateSource.addEventListener("input", () => updateIntegrationStepState());
    els.integrateMode.addEventListener("change", () => updateIntegrationStepState("mode"));

    async function refresh() {
      try {
        render(await requestApi("/api/state"));
      } catch (error) {
        els.lastMessage.textContent = error.message;
      }
    }

    async function run(labelKey, fn) {
      els.lastMessage.textContent = `${t(labelKey)}...`;
      try {
        const result = await fn();
        els.lastMessage.textContent = result.message || t("done");
        render(result.state || await requestApi("/api/state"));
      } catch (error) {
        els.lastMessage.textContent = error.message;
      }
    }

    async function sendChat() {
      const message = els.chatInput.value.trim();
      if (!message) return;
      els.sendChat.disabled = true;
      els.lastMessage.textContent = `${t("sendingChat")}...`;
      try {
        const result = await postApi("/api/chat", {
          message,
          planner: els.chatPlanner.value,
          auto_step: els.chatAutoStep.checked
        });
        els.chatInput.value = "";
        els.chatInput.dataset.touched = "";
        els.lastMessage.textContent = result.message || t("done");
        render(result.state || await requestApi("/api/state"));
        els.chatInput.focus();
      } catch (error) {
        els.lastMessage.textContent = error.message;
      } finally {
        els.sendChat.disabled = false;
      }
    }

    async function integrateHardware() {
      const source = els.integrateSource.value.trim();
      if (!source) {
        els.lastMessage.textContent = "Source cannot be empty.";
        return;
      }
      els.integrate.disabled = true;
      els.lastMessage.textContent = `${t("integrating")}...`;
      try {
        const result = await postApi("/api/integrate", {
          source,
          name: els.integrateName.value,
          model: els.integrateModel.value,
          llm: els.integrateMode.value === "llm"
        });
        els.lastMessage.textContent = result.message || t("done");
        renderIntegrationResult(result);
        render(result.state || await requestApi("/api/state"));
      } catch (error) {
        els.lastMessage.textContent = error.message;
      } finally {
        els.integrate.disabled = false;
      }
    }

    els.setup.addEventListener("click", () => run("settingUp", () => postApi("/api/setup")));
    els.reset.addEventListener("click", () => run("resetting", () => postApi("/api/setup", { force: true })));
    els.startWatch.addEventListener("click", () => run("startingWatch", () => postApi("/api/watch/start")));
    els.stepWatch.addEventListener("click", () => run("runningStep", () => postApi("/api/watch/step")));
    els.demo.addEventListener("click", () => run("runningDemo", () => postApi("/api/demo")));
    els.refresh.addEventListener("click", () => run("refreshing", () => requestApi("/api/state")));
    els.sendChat.addEventListener("click", sendChat);
    els.chatInput.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendChat();
      }
    });
    els.integrate.addEventListener("click", integrateHardware);

    setLanguage(lang);
    updateIntegrationStepState();
    refresh();
