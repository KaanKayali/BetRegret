import React from "react";
import styles from "./Chatfield.module.scss";
import arrowup from "../../assets/arrow-up.png";
import arrow from "../../assets/arrow-white.png";

export default function Chatfield() {
  return (
    <>
      <div className={styles.container}>
        <div className={styles.chatfield}>
          <input type="text" className="" placeholder="Ask a question" />
          <button className={styles.button}>
            <img src={arrow} />
          </button>
        </div>
      </div>
    </>
  );
}
