const DASHBOARD_URL = "https://aulanybo.up.railway.app";

// Listen for cookie changes on aula.dk
chrome.cookies.onChanged.addListener(async (changeInfo) => {
  const cookie = changeInfo.cookie;

  // We care about PHPSESSID being set on aula.dk
  if (
    cookie.domain.includes("aula.dk") &&
    cookie.name === "PHPSESSID" &&
    !changeInfo.removed
  ) {
    console.log("Aula PHPSESSID changed, syncing session...");
    await syncSession();
  }
});

async function syncSession() {
  try {
    // Get both cookies
    const phpSessId = await chrome.cookies.get({
      url: "https://www.aula.dk",
      name: "PHPSESSID"
    });
    const csrfToken = await chrome.cookies.get({
      url: "https://www.aula.dk",
      name: "Csrfp-Token"
    });

    if (!phpSessId || !csrfToken) {
      console.log("Missing cookies, skipping sync");
      return;
    }

    // Get stored API key
    const { apiKey } = await chrome.storage.local.get("apiKey");
    if (!apiKey) {
      console.warn("No API key stored. Visit the dashboard to set it.");
      return;
    }

    // POST to dashboard
    const res = await fetch(`${DASHBOARD_URL}/api/refresh-session`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey
      },
      body: JSON.stringify({
        phpsessid: phpSessId.value,
        csrf_token: csrfToken.value
      })
    });

    const data = await res.json();
    if (data.ok) {
      console.log("Session synced successfully!");
      // Notify content script to redirect back to dashboard
      const tabs = await chrome.tabs.query({ url: "https://www.aula.dk/*" });
      for (const tab of tabs) {
        chrome.tabs.sendMessage(tab.id, { action: "sessionSynced" });
      }
    } else {
      console.error("Session sync failed:", data);
    }
  } catch (e) {
    console.error("Error syncing session:", e);
  }
}
