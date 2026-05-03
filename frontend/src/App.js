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

  const handleInput = (e) => {
    setInput(e.target.value);
    console.log(input);
  };

  const sendMessage = async (e) => {
    const newMessage = {
      role: "HumanMessage",
      content: input,
    };
    setMessages((prev) => [...prev, newMessage]);
    setInput("");
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
  };

  return (
    <>
      <div className={styles.app}>
        <Header />
        <Chatview messages={messages} />
        <Chatfield
          input={input}
          handleInput={handleInput}
          handleSubmit={sendMessage}
        />
      </div>
    </>
  );
}
