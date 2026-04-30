import styles from "./App.module.scss";
import Header from "./components/Header/Header";
import Chatfield from "./components/Chatfield/Chatfield";
import UserInput from "./components/UserInput/UserInput";
import Chatview from "./components/Chatview/Chatview";
import { useState } from "react";

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: "HumanMessage",
      content: "Who is gonna win the game Bayern against PSG",
    },
    {
      role: "AIMessage",
      content: `Bayern are winning this week because somewhere deep inside the Allianz Arena, FC Bayern Munich have a secret setting called “Champions League Mode” — and once it’s activated, even WiFi signals start pressing high.
Meanwhile Paris Saint-Germain will show up with more drip than a Milan fashion show, but Bayern will politely remind them this isn’t runway practice — it’s 90 minutes of controlled chaos, German engineering style.
Also let’s be honest: if Thomas Müller starts smiling mid-game, it’s already over. That man doesn’t smile unless he’s mentally three passes ahead and planning the assist after the assist.
And if things somehow get shaky? Don’t worry — Bayern’s DNA is basically:
“Lose the ball → win it back → score → act like it was always the plan.”
PSG might have stars, but Bayern is the constellation. 🌟`,
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleInput = (e) => {
    setInput(e.target.value);
  };

  const handleClick = async () => {
    if (loading || !input.trim()) return;

    const userMessage = {
      role: "HumanMessage",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
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
        <Chatview messages={messages} />
        <Chatfield
          input={input}
          handleInput={handleInput}
          handleClick={handleClick}
          loading={loading}
        />
      </div>
    </>
  );
}
