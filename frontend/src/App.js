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

  const handleInput = (e) => {
    setInput(e.target.value);
    console.log(input);
  };

  const handleClick = (e) => {
    const newMessage = {
      role: "HumanMessage",
      content: input,
    };
    setMessages((prev) => [...prev, newMessage]);
    setInput("");

    setTimeout(() => {
      setMessages((prev) => [...prev, prev[1]]);
    }, 10000);
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
        />
      </div>
    </>
  );
}
