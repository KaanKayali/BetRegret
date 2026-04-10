import styles from "./App.module.scss";
import Header from "./components/Header/Header";
import Chatfield from "./components/Chatfield/Chatfield";

export default function App() {
  return (
    <>
      <div className={styles.app}>
        <Header />
        <Chatfield />
      </div>
    </>
  );
}
