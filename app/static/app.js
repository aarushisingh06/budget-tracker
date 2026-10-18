// Ask for confirmation before submitting forms marked with data-confirm
// (used for deletes). Kept in a file rather than inline so the
// Content-Security-Policy can block all inline scripts.
document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});
