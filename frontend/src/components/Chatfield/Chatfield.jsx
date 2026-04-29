import React from "react";
import styles from "./Chatfield.module.scss";
import arrowup from "../../assets/arrow-up.png";
import arrow from "../../assets/arrow-white.png";

export default function Chatfield(props) {
  const { input, handleInput, handleClick } = props;
  return (
    <>
      <div className={styles.container}>
        <div className={styles.chatfield}>
          <input
            type="text"
            placeholder="Ask a question"
            value={input}
            onChange={handleInput}
          />
          <button onClick={handleClick} className={styles.button}>
            <img src={arrow} />
          </button>
        </div>
      </div>
    </>
  );
}
