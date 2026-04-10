import React from "react";
import styles from "./Header.module.scss";
import logo from "../../assets/logo.png";

export default function Header() {
  return (
    <div className={styles.header}>
      <img src={logo} />
      <div className={styles.heading}>BET SMARTER. WIN BIGGER.</div>
    </div>
  );
}
