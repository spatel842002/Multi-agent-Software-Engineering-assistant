import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CitationList } from "./CitationList";

describe("CitationList", () => {
  it("renders a file:line-line entry for each citation", () => {
    render(
      <CitationList
        citations={[
          { file_path: "app/main.py", start_line: 10, end_line: 20 },
          { file_path: "app/db.py", start_line: 1, end_line: 5 },
        ]}
      />,
    );
    expect(screen.getByText("app/main.py:10-20")).toBeInTheDocument();
    expect(screen.getByText("app/db.py:1-5")).toBeInTheDocument();
  });

  it("shows an explanatory message when there are no citations", () => {
    render(<CitationList citations={[]} />);
    expect(screen.getByText(/no citations were resolved/i)).toBeInTheDocument();
  });
});
