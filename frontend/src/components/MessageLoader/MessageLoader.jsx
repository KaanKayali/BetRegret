import React from "react";
import styles from "./MessageLoader.module.scss";
import football from "../../assets/football.png";

export default function MessageLoader() {
  return (
    <div className={styles.container}>
      <img src={football} />
      <div>Loading ...</div>
    </div>
  );
}
