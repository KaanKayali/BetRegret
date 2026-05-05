import React from "react";
import styles from "./AIMessage.module.scss";

function parseInlineStyles(text) {
  const parts = text.split(/(\*\*[\s\S]+?\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function parseContent(content) {
  const lines = content.split(/\r?\n/);
  const nodes = [];
  let listItems = [];

  const flushList = () => {
    if (listItems.length > 0) {
      nodes.push(
        <ul key={`list-${nodes.length}`} className={styles.list}>
          {listItems.map((item, index) => (
            <li key={index}>{parseInlineStyles(item)}</li>
          ))}
        </ul>,
      );
      listItems = [];
    }
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    const listMatch = trimmed.match(/^(-|\*|\d+\.)\s+(.*)$/);

    if (trimmed === "") {
      flushList();
      nodes.push(<br key={`br-${index}`} />);
    } else if (listMatch) {
      listItems.push(listMatch[2]);
    } else {
      flushList();
      nodes.push(
        <p key={`p-${index}`} className={styles.paragraph}>
          {parseInlineStyles(line)}
        </p>,
      );
    }
  });

  flushList();
  return nodes;
}

export default function AIMessage(props) {
  const { content } = props;
  return <div className={styles.container}>{parseContent(content)}</div>;
}
