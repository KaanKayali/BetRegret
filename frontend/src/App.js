import styles from "./App.module.scss";
import Header from "./components/Header/Header";
import Chatfield from "./components/Chatfield/Chatfield";
import UserInput from "./components/UserInput/UserInput";
import Chatview from "./components/Chatview/Chatview";

export default function App() {
  return (
    <>
      <div className={styles.app}>
        <Header />
        <Chatview />
        <Chatfield />
      </div>
    </>
  );
}
