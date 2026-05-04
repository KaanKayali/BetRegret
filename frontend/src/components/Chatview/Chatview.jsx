import React from "react";
import styles from "./Chatview.module.scss";
import UserInput from "../UserInput/UserInput";
import AIMessage from "../AIMessage/AIMessage";
import MessageLoader from "../MessageLoader/MessageLoader";

export default function Chatview(props) {
  const { messages, messageLoading } = props;
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
        {messageLoading && <MessageLoader />}
      </div>
    </div>
  );
}
