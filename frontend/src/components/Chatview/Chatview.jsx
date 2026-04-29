import React from "react";
import styles from "./Chatview.module.scss";
import UserInput from "../UserInput/UserInput";
import AIMessage from "../AIMessage/AIMessage";

export default function Chatview(props) {
  const { messages } = props;
  return (
    <div className={styles.container}>
      <div className={styles.chatview}>
        {messages.map((item) =>
          item.role == "HumanMessage" ? (
            <UserInput content={item.content} />
          ) : (
            <AIMessage content={item.content} />
          ),
        )}
        {/* <UserInput />
        <AIMessage /> */}
      </div>
    </div>
  );
}
