const features = [
  {
    number: "01",
    title: "Stock Analysis",
    description:
      "Explore price history and understand technical indicators, including RSI, MACD, and Bollinger Bands.",
    detail: "Understand the movement",
  },
  {
    number: "02",
    title: "Watchlists",
    description:
      "Keep the companies you follow in one place, with an account and a watchlist that stays with you.",
    detail: "Follow what interests you",
  },
  {
    number: "03",
    title: "ML Predictions",
    description:
      "Investigate next-trading-day price direction using historical data and measurable model outputs.",
    detail: "Explore a hypothesis",
  },
  {
    number: "04",
    title: "Prediction Evaluation",
    description:
      "Compare predictions with observed outcomes and learn where models succeed, struggle, and change.",
    detail: "Measure the evidence",
  },
];

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="header shell">
        <a className="brand" href="#" aria-label="StockSight home">
          <span className="brand-mark" aria-hidden="true">
            S<span>↗</span>
          </span>
          StockSight<span className="brand-dot">.</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#explore">Our direction</a>
          <a href="#project">
            The project <span aria-hidden="true">↗</span>
          </a>
        </nav>
      </header>

      <main id="main">
        <section className="hero shell" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="status-dot" /> A new perspective, in progress
            </p>
            <h1 id="hero-title">
              Less noise.
              <br />
              More <em>insight.</em>
            </h1>
            <p className="intro">
              A clearer view of the market starts with better questions. We’re
              building a space to explore stocks, test ideas, and learn from the
              evidence.
            </p>
            <a className="button" href="#explore">
              Explore what’s ahead <span aria-hidden="true">↘</span>
            </a>
            <p className="hero-note">Early scaffold · Features coming soon</p>
          </div>
          <aside className="perspective" aria-labelledby="perspective-title">
            <div className="panel-top">
              <span>THE STOCKSIGHT APPROACH</span>
              <span aria-hidden="true">↗</span>
            </div>
            <div className="orbit" aria-hidden="true">
              <div className="orbit-inner">
                <span>S.</span>
              </div>
              <span className="orbit-point" />
            </div>
            <h2 id="perspective-title">
              Curiosity.
              <br />
              Backed by evidence.
            </h2>
            <p>
              Observe the data. Test a hypothesis.
              <br />
              Measure what actually happened.
            </p>
            <div className="panel-bottom">
              <span>Research, then reason.</span>
              <span>01 / 04</span>
            </div>
          </aside>
        </section>

        <section
          className="explore shell"
          id="explore"
          aria-labelledby="explore-title"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">WHAT WE’RE BUILDING</p>
              <h2 id="explore-title">Four ways to look closer.</h2>
            </div>
            <p>
              One connected learning experience.
              <br />
              All four areas are planned.
            </p>
          </div>
          <div className="feature-grid">
            {features.map((feature) => (
              <article className="feature" key={feature.number}>
                <div className="feature-top">
                  <span>{feature.number}</span>
                  <span className="badge">Coming soon</span>
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
                <div className="feature-detail">
                  {feature.detail}
                  <span aria-hidden="true">↗</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section
          className="project shell"
          id="project"
          aria-labelledby="project-title"
        >
          <p className="eyebrow">BUILT TO LEARN</p>
          <div>
            <h2 id="project-title">An experiment in understanding.</h2>
            <p>
              StockSight is a CSE 4095 Agentic Programming team project at the
              University of Connecticut. We’re starting with a clean foundation
              and building thoughtfully, one question at a time.
            </p>
          </div>
        </section>
      </main>

      <footer className="footer shell">
        <span className="footer-brand">StockSight.</span>
        <p>
          For education and research only. Not financial advice.
          <br />
          Future predictions will be uncertain and will not guarantee returns.
        </p>
        <span className="footer-note">Made with curiosity.</span>
      </footer>
    </>
  );
}
