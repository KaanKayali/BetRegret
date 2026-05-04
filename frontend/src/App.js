import styles from "./App.module.scss";
import Header from "./components/Header/Header";
import Chatfield from "./components/Chatfield/Chatfield";
import UserInput from "./components/UserInput/UserInput";
import Chatview from "./components/Chatview/Chatview";
import { useState } from "react";
import { postMessage } from "./services/services";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [messageLoading, setMessageLoading] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleInput = (e) => {
    setInput(e.target.value);
  };

  const sendMessage = async () => {
    if (loading || !input.trim()) return;

    const userMessage = {
      role: "HumanMessage",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setMessageLoading(true);
    
    const message = await postMessage(newMessage.content);
    if (message.error) {
      console.log(message.error);
      setMessageLoading(false);
      return;
    }
    const newResponse = {
      role: "AIMessage",
      content: message.reply,
    };
    setMessages((prev) => [...prev, newResponse]);
    setMessageLoading(false);
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input }),
      });

      if (!response.ok) {
        throw new Error("Network response was not ok");
      }

      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "AIMessage", content: data.reply },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "AIMessage",
          content: "Fehler beim Verbinden mit dem Server.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className={styles.app}>
        <Header />
        <Chatview messages={messages} messageLoading={messageLoading} />
        <Chatfield
          input={input}
          handleInput={handleInput}
          handleClick={sendMessage}
          loading={loading}
        />
      </div>
    </>
  );
}
