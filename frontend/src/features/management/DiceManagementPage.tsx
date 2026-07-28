import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { DiceSetManager } from "../quick-tools/DiceSetManager";

export function DiceManagementPage() {
  const { notify } = useApp();

  return (
    <div className="page dice-management-page" data-component-type="view" data-theme="arcane">
      <header className="page-header">
        <div>
          <p className="eyebrow">Amministrazione</p>
          <h1>Gestisci Dadi</h1>
          <p>
            Crea, modifica e archivia i set di dadi. Assegna texture, colori e
            forme per ogni dado. I set attivi compaiono nelle impostazioni e
            nel selettore dei dadi.
          </p>
        </div>
        <div className="button-row">
          <Link className="button secondary" to="/tools">
            Tutti gli strumenti
          </Link>
        </div>
      </header>

      <DiceSetManager notify={notify} />
    </div>
  );
}
