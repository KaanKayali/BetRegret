import React from "react";
import styles from "./Chatfield.module.scss";
import arrow from "../../assets/arrow-white.png";

export default function Chatfield(props) {
  const { input, handleInput, handleClick, loading = false } = props;

  return (
    <>
      <div className={styles.container}>
        <div className={styles.chatfield}>
          <input
            type="text"
            placeholder="Ask a question"
            value={input}
            onChange={handleInput}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleClick(e);
            }}
            disabled={loading}
          />
          <button
            onClick={handleClick}
            className={styles.button}
            disabled={loading}
            type="button"
          >
            <img src={arrow} alt="Send" />
          </button>
        </div>
      </div>
    </>
  );
}
