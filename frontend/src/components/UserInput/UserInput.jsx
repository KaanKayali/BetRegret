import React from "react";
import styles from "./UserInput.module.scss";

export default function UserInput(props) {
  const { content } = props;
  return (
    <div className={styles.container}>
      <div className={styles.userinput}>{content}</div>
    </div>
  );
}
