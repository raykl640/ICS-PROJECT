import { screen } from "@testing-library/react";
import { renderIn } from "../test/render";
import { ReferralFooter } from "./ReferralFooter";

test("renders nothing without verified entries (the shipped file has none)", () => {
  const { container } = renderIn(<ReferralFooter />);
  expect(container).toBeEmptyDOMElement();
  const unverified = renderIn(<ReferralFooter entries={[{ name: "Unchecked Office", verified: false }]} />);
  expect(unverified.container).toBeEmptyDOMElement();
});

test("shows only verified entries in the active language", () => {
  renderIn(
    <ReferralFooter
      entries={[
        { name: "Example Aid Office", description: { en: "Free help", sw: "Msaada bure" }, verified: true },
        { name: "Unchecked Office", verified: false },
      ]}
    />,
    "sw",
  );
  expect(screen.getByText("Example Aid Office")).toBeInTheDocument();
  expect(screen.getByText("Msaada bure")).toBeInTheDocument();
  expect(screen.queryByText("Unchecked Office")).not.toBeInTheDocument();
});
