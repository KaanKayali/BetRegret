import React from "react";
import styles from "./AIMessage.module.scss";

export default function AIMessage(props) {
  const { content } = props;
  return (
    <>
      <div className={styles.container}>{content}</div>
    </>
  );
}
