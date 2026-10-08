/* ─────────────────────────────────────────────────────────────────
   PATCH INSTRUCTIONS FOR Home.jsx  (do NOT replace the whole file)
   ─────────────────────────────────────────────────────────────────

   Find the existing header / navbar element in Home.jsx.
   It likely looks something like one of these patterns:

     Pattern A — plain div header:
       <div className="header">
         <h1>Liver Tumour Segmentation</h1>
       </div>

     Pattern B — nav bar with logo:
       <nav className="navbar">
         <span className="logo">...</span>
       </nav>

   ADD the "Demo Mode" link next to your existing title.

   ── Minimal JSX to add ───────────────────────────────────────── */

// 1. No import needed — it's a plain <a> link, not React Router.

// 2. Paste this button/link wherever your header content lives:

const DemoModeButton = () => (
  <a
    href="/demo"
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "6px",
      padding: "5px 13px",
      borderRadius: "7px",
      border: "1px solid #30363d",
      background: "transparent",
      color: "#8b949e",
      fontSize: "12px",
      fontFamily: "inherit",
      textDecoration: "none",
      letterSpacing: "0.04em",
      transition: "all 0.15s",
      whiteSpace: "nowrap",
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.borderColor = "#f97316";
      e.currentTarget.style.color = "#f97316";
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.borderColor = "#30363d";
      e.currentTarget.style.color = "#8b949e";
    }}
  >
    <span style={{ fontSize: "13px" }}>🔬</span>
    Demo Mode
  </a>
);

/*
   3. In your header JSX, change from:

       <div className="header">
         <h1>Liver Tumour Segmentation</h1>
       </div>

      To:

       <div className="header" style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
         <h1>Liver Tumour Segmentation</h1>
         <DemoModeButton />
       </div>

   That's the entire change to Home.jsx.
   ─────────────────────────────────────────────────────────────── */

export default DemoModeButton;
