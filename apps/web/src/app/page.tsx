import { redirect } from "next/navigation";

export default function Home() {
  // Until the workspace exists (Phase 1), everyone lands on sign-in.
  redirect("/login");
}
