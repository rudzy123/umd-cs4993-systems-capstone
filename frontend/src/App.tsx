import { Link, Route, Routes } from "react-router-dom";

import { HomePage } from "./pages/HomePage";
import { JobDetailPage } from "./pages/JobDetailPage";

export function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <header className="site-header">
        <p className="course">UMD CS 4993 Systems Capstone</p>
        <Link className="brand" to="/">
          Northstar Job Lab
        </Link>
        <p className="tagline">A local job queue for small computational workloads.</p>
      </header>
      <main id="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        </Routes>
      </main>
      <footer>
        <p>Local lab only. Do not expose this stack to the public internet.</p>
      </footer>
    </>
  );
}
