import React, { useState } from "react";
import styles from "./Chatfield.module.scss";
import arrow from "../../assets/arrow-white.png";

export default function Chatfield(props) {
  const { input, handleInput, handleSubmit } = props;
  const [text, setText] = useState("");
  const [messages, setMessages] = useState([]);

  return (
    <div className={styles.container}>
      <div className={styles.chatfield}>
        <input
          type="text"
          value={input}
          placeholder="Ask a question"
          onChange={handleInput}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
          }}
        />
        <button
          className={styles.button}
          onClick={handleSubmit}
          // disabled={loading}
        >
          <img src={arrow} alt="Send" />
        </button>
      </div>

      {/* <div className={styles.messageArea}>
        {messages.map((msg, index) => (
          <div
            key={index}
            className={
              msg.role === "bot" ? styles.botMessage : styles.userMessage
            }
          >
            {msg.text}
          </div>
        ))}
      </div> */}
    </div>
  );
}
