import Analysis from './Analysis.jsx';
const sections = [
  { number: '01', title: 'Stock analysis', status: 'Historical demo' },
  { number: '02', title: 'Watchlists', status: 'Planned' },
  { number: '03', title: 'Predictions', status: 'Planned' },
  { number: '04', title: 'Evaluation', status: 'Planned' },
];
const repo = 'https://github.com/noahsteinberg/StockSight';

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="masthead wrap">
        <a className="brand" href="#" aria-label="StockSight home">StockSight<span aria-hidden="true"> /</span></a>
        <nav aria-label="Main navigation">
          <a href="#analysis">Analysis</a>
          <a href="#project">Project</a>
          <a href={repo}>GitHub <span aria-hidden="true">↗</span></a>
        </nav>
      </header>
      <main id="main" className="wrap" tabIndex="-1">
        <Analysis />
        <section id="scope" className="scope" aria-labelledby="scope-title">
          <div className="section-heading"><h2 id="scope-title">Project scope</h2><span>Planned capabilities</span></div>
          <ol className="scope-list">
            {sections.map(section => (
              <li key={section.number}>
                <span className="row-number" aria-hidden="true">{section.number}</span>
                <h3>{section.title}</h3>

                <span className={section.status === 'Next up' ? 'row-status next' : 'row-status'}>{section.status}</span>
              </li>
            ))}
          </ol>
        </section>
        <section id="project" className="project" aria-labelledby="project-title">
          <div><span className="note-label">THE PROJECT</span><h2 id="project-title">Built at UConn.</h2></div>
          <div className="project-copy"><p>A CSE 4095 Agentic Programming team project by Noah Steinberg, Gavin Javier Pino, Parth Sachdev, and Vladislav Lagutin.</p><a className="text-link" href={`${repo}/blob/main/SPECIFICATION.md`}>Read the specification <span aria-hidden="true">↗</span></a></div>
        </section>
      </main>
      <footer className="footer wrap"><span>StockSight</span><p>For education and research. Not financial advice.</p><a href="#">Back to top ↑</a></footer>
    </>
  );
}
