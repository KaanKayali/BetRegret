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

    const newHistory = [...messages, userMessage];
    setMessages(newHistory);
    setInput("");
    setLoading(true);
    setMessageLoading(true);

    const message = await postMessage(newHistory);

    if (message.error) {
      console.log(message.error);
      setMessages((prev) => [
        ...prev,
        {
          role: "AIMessage",
          content: "Fehler beim Verbinden mit dem Server.",
        },
      ]);
    } else {
      const newResponse = {
        role: "AIMessage",
        content: message.reply,
      };
      setMessages((prev) => [...prev, newResponse]);
    }

    setMessageLoading(false);
    setLoading(false);
  };

  return (
    <>
      <div className={styles.app}>
        <Header />
        <Chatview messages={messages} messageLoading={messageLoading} />
        <Chatfield
          input={input}
          handleInput={handleInput}
          handleSubmit={sendMessage}
          loading={loading}
        />
      </div>
    </>
  );
}
