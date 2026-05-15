function gcdExtractPage(mode) {
  const selection = window.getSelection ? String(window.getSelection()).trim() : "";
  const readableText = Array.from(document.querySelectorAll("article, main"))
    .map((node) => node.innerText || "")
    .join("\n\n")
    .trim();
  const bodyText = document.body ? document.body.innerText || "" : "";
  const text = mode === "selection" ? selection : readableText || bodyText;

  return {
    url: location.href,
    title: document.title || location.href,
    text,
    html: document.documentElement ? document.documentElement.outerHTML : "",
    source_platform: location.hostname.replace(/^www\./, ""),
    captured_at: new Date().toISOString()
  };
}
