import React from "react";
import styles from "./Chatview.module.scss";
import UserInput from "../UserInput/UserInput";
import AIMessage from "../AIMessage/AIMessage";
export default function Chatview() {
  return (
    <div className={styles.container}>
      <div className={styles.chatview}>
        <UserInput />
        <AIMessage />
      </div>
    </div>
  );
}
