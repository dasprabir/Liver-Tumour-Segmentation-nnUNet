/* ─────────────────────────────────────────────────────────────────
   PATCH INSTRUCTIONS FOR App.jsx  (minimal — 2 lines added)
   ─────────────────────────────────────────────────────────────────

   Your current App.jsx uses a simple pathname router like this:

     import Home from "./pages/Home";
     import Beta3D from "./pages/Beta3D";

     function App() {
       const path = window.location.pathname;
       if (path === "/beta-3d") return <Beta3D />;
       return <Home />;
     }

   ADD the Demo import and route. Final result:
   ─────────────────────────────────────────────────────────────── */

import Home from "./pages/Home";
import Beta3D from "./pages/Beta3D";
import Demo from "./pages/Demo";          // ← ADD THIS LINE

function App() {
  const path = window.location.pathname;
  if (path === "/beta-3d") return <Beta3D />;
  if (path === "/demo")    return <Demo />;  // ← ADD THIS LINE
  return <Home />;
}

export default App;

/*
   That's the entire change to App.jsx.
   No other files need editing.
   ─────────────────────────────────────────────────────────────── */
