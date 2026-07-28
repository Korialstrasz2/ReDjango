import { Link } from "react-router-dom";
import { useApp } from "../../App";

export function ManagementHub() {
  const { settings } = useApp();
  return <div className="page management-page">
    <header className="page-header"><div><p className="eyebrow">Strumenti riservati</p><h1>Gestione del gioco</h1></div></header>
    <section className="management-launcher" data-component-type="grid" data-theme="default">
      <Link className="management-tool-card" to="/tools/characters" data-component-type="card" data-theme="parchment">
        <span className="management-tool-icon" aria-hidden="true">♙</span>
        <span><small>Archivio e relazioni</small><strong>Gestione Personaggi</strong><p>Modifica schede e record collegati, trova gli orfani e controlla ogni eliminazione prima di confermarla.</p></span>
        <b aria-hidden="true">Apri →</b>
      </Link>
      <Link className="management-tool-card" to="/tools/items" data-component-type="card" data-theme="gold">
        <span className="management-tool-icon" aria-hidden="true">◇</span>
        <span><small>Catalogo e confronto</small><strong>Gestione Oggetti</strong><p>Cerca, filtra, crea e modifica gli oggetti; confronta due record e copia i valori in sicurezza.</p></span>
        <b aria-hidden="true">Apri →</b>
      </Link>
      <Link className="management-tool-card" to="/tools/skills" data-component-type="card" data-theme="arcane">
        <span className="management-tool-icon" aria-hidden="true">✦</span>
        <span><small>Catalogo, struttura e migrazione</small><strong>Gestione Skill</strong><p>Controlla skill, magie, famiglie e gruppi; correggi in una coda dedicata i record Elder rimasti ambigui.</p></span>
        <b aria-hidden="true">Apri →</b>
      </Link>
      <Link className="management-tool-card" to="/tools/units" data-component-type="card" data-theme="arcane">
        <span className="management-tool-icon" aria-hidden="true">⚔</span>
        <span><small>Archetipi e generazione rapida</small><strong>Gestione Unit</strong><p>Configura umanoidi, animali e creature; prova Skill, crescita ed equipaggiamento con lo stesso generatore usato in Combattimento.</p></span>
        <b aria-hidden="true">Apri →</b>
      </Link>
      <Link className="management-tool-card" to="/tools/shops" data-component-type="card" data-theme="gold">
        <span className="management-tool-icon" aria-hidden="true">¤</span>
        <span><small>Territorio, assortimenti e profili</small><strong>Gestione Negozi</strong><p>Ordina il mondo commerciale, configura i tipi di negozio e assegna profili riproducibili alle scorte.</p></span>
        <b aria-hidden="true">Apri →</b>
      </Link>
      <Link className="management-tool-card" to="/tools/dungeon" data-component-type="card" data-theme="arcane">
        <span className="management-tool-icon" aria-hidden="true">⌘</span>
        <span><small>In lavorazione</small><strong>Aiuto Dungeon</strong><p>Trappole, stanze, ritmo e complicazioni da consultare al tavolo. Strumento del Master, non una guida da leggere.</p></span>
        <b aria-hidden="true">Apri →</b>
      </Link>
      {settings.security.canManageAdminSettings && <Link className="management-tool-card" to="/tools/themes" data-component-type="card" data-theme="parchment">
        <span className="management-tool-icon" aria-hidden="true">◐</span>
        <span><small>Colori, sfondi e trasparenze</small><strong>Gestione Temi</strong><p>Modifica i temi con anteprima dal vivo, assegna gli sfondi a ogni schermata e scegli il tema predefinito.</p></span>
        <b aria-hidden="true">Apri →</b>
      </Link>}
      {settings.security.canManageAdminSettings && <Link className="management-tool-card" to="/tools/variables" data-component-type="card" data-theme="arcane">
        <span className="management-tool-icon" aria-hidden="true">ƒ</span>
        <span><small>Formule e regole globali</small><strong>Gestione Variabili</strong><p>Controlla valori base, formule, Stanchezza e prezzi Skill con validazione obbligatoria prima del salvataggio.</p></span>
        <b aria-hidden="true">Apri →</b>
      </Link>}
    </section>
  </div>;
}
