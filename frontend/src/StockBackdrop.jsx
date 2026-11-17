// Decorative illustration only; no live market feed.
export default function StockBackdrop() {
  return (<div className="ss-scene" aria-hidden="true">
<svg className="ss-chart" viewBox="0 0 1440 900" preserveAspectRatio="none" fill="none">
<defs>
<linearGradient id="ss-fill" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#5f9fdf" stopOpacity=".25"/><stop offset="1" stopColor="#5f9fdf" stopOpacity="0"/></linearGradient>
<pattern id="ss-grid" width="120" height="100" patternUnits="userSpaceOnUse"><path d="M120 0H0V100" stroke="#88b6ed" strokeOpacity=".12"/></pattern>
</defs>
<path fill="url(#ss-grid)" d="M0 0H1440V900H0Z"/>
<path d="M0 700L60 660L100 680L150 600L200 630L250 540L300 570L350 490L400 530L450 440L500 480L550 410L600 460L650 350L700 380L750 320L800 360L850 290L900 340L950 240L1000 275L1050 210L1100 260L1150 170L1200 210L1250 140L1300 170L1350 100L1440 130V900H0Z" fill="url(#ss-fill)"/>
<path d="M0 700L60 660L100 680L150 600L200 630L250 540L300 570L350 490L400 530L450 440L500 480L550 410L600 460L650 350L700 380L750 320L800 360L850 290L900 340L950 240L1000 275L1050 210L1100 260L1150 170L1200 210L1250 140L1300 170L1350 100L1440 130" stroke="#7ebcfc" strokeWidth="4" strokeLinejoin="round"/>
</svg>
<svg className="ss-chart ss-chart-secondary" viewBox="0 0 1440 900" preserveAspectRatio="none" fill="none"><path d="M0 580L90 620L180 530L270 570L360 460L450 510L540 450L630 520L720 390L810 430L900 310L990 350L1080 290L1170 360L1260 250L1350 290L1440 220" stroke="#67d6c6" strokeWidth="3"/></svg>
</div>);
}
