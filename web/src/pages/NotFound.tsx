import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui";

export default function NotFound() {
  const navigate = useNavigate();
  return (
    <div className="mx-auto max-w-[640px] px-8 py-20">
      <h1 className="text-display font-semibold text-ink">This page does not exist</h1>
      <p className="mt-2 text-lead text-ink-2">The link may be old, or the proposal was removed.</p>
      <Button className="mt-6" variant="primary" onClick={() => navigate("/")}>Go to Home</Button>
    </div>
  );
}
