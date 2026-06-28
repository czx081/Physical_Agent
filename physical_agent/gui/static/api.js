async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "Request failed");
      return data;
    }

async function post(path, payload = {}) {
      return api(path, { method: "POST", body: JSON.stringify(payload) });
    }

window.GuiApi = { api, post };
