export async function postMessage(content) {
  try {
    const response = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: content }),
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }
    const message = await response.json();
    return message;
  } catch (error) {
    return { error: error.message };
  }
}
