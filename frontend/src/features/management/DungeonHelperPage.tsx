import { Link } from "react-router-dom";

export function DungeonHelperPage() {
  return <div className="page management-page dungeon-helper-page">
    <header className="page-header">
      <div>
        <p className="eyebrow">Strumenti riservati</p>
        <h1>Aiuto Dungeon</h1>
        <p>Trappole, stanze, ritmo e complicazioni da consultare al tavolo mentre il gruppo esplora.</p>
      </div>
      <div className="button-row"><Link className="button secondary" to="/tools">Tutti gli strumenti</Link></div>
    </header>
    <section className="panel dungeon-helper-wip" data-component-type="card" data-theme="parchment">
      <p className="eyebrow">In lavorazione</p>
      <h2>Strumento non ancora disponibile</h2>
      <p>
        Questa postazione ospiterà l'aiuto alla costruzione dei dungeon: idee di trappole, stanze e
        incontri consultabili durante la sessione, generatori rapidi e complicazioni da pescare al volo.
      </p>
      <p>
        Non è una guida da leggere: è pensata come strumento del Master, quindi resterà qui e non
        nella sezione Guide.
      </p>
    </section>
  </div>;
}
