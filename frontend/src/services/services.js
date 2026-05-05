export async function postMessage(messages) {
  try {
    const response = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: messages }),
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }
    const message = await response.json();
    console.log(message);
    return message;
  } catch (error) {
    return { error: error.message };
  }
}
