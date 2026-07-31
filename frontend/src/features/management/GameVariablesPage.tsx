import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Modal } from "../../components/Modal";
import { command, getData, type ApiClientError } from "../../lib/api";
import type {
  GameVariableField,
  GameVariablesData,
  GameVariablesValidation,
} from "../../lib/types";
import { useApp } from "../../App";


type Draft = Record<string, unknown>;
type Section = "all" | GameVariableField["section"];


function flatValues(data: GameVariablesData): Draft {
  return Object.fromEntries(
    data.groups.flatMap((group) =>
      group.fields.map((field) => [field.id, field.value])
    ),
  );
}


function sameValue(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}


function displayDefaultValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.map(String).join(", ") : "Nessuno";
  }
  if (value === "" || value === null || value === undefined) {
    return "Nessuno";
  }
  return String(value);
}


function VariableControl({
  field,
  value,
  onChange,
}: {
  field: GameVariableField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (field.valueType === "multi_select") {
    const selected = Array.isArray(value) ? value.map(String) : [];
    return (
      <fieldset className="game-variable-multi">
        <legend className="sr-only">{field.label}</legend>
        {field.choices.map((choice) => (
          <label key={choice.value}>
            <input
              type="checkbox"
              checked={selected.includes(choice.value)}
              onChange={(event) => {
                onChange(
                  event.target.checked
                    ? [...selected, choice.value]
                    : selected.filter((entry) => entry !== choice.value),
                );
              }}
            />
            <span>{choice.label}</span>
          </label>
        ))}
      </fieldset>
    );
  }

  if (field.valueType === "formula") {
    return (
      <textarea
        className="game-variable-formula"
        value={String(value ?? "")}
        rows={3}
        spellCheck={false}
        maxLength={field.constraints.maximumLength}
        onChange={(event) => onChange(event.target.value)}
        aria-label={field.label}
      />
    );
  }

  if (field.valueType === "text") {
    return (
      <textarea
        value={String(value ?? "")}
        rows={6}
        maxLength={field.constraints.maximumLength}
        onChange={(event) => onChange(event.target.value)}
        aria-label={field.label}
      />
    );
  }

  return (
    <span className="game-variable-number">
      <input
        type="number"
        value={String(value ?? "")}
        min={field.constraints.minimum}
        max={field.constraints.maximum}
        step={field.constraints.step ?? 1}
        onChange={(event) => onChange(event.target.value)}
        aria-label={field.label}
      />
      {field.constraints.suffix && <b>{field.constraints.suffix}</b>}
    </span>
  );
}


function ValidationReview({
  validation,
  saving,
  onClose,
  onConfirm,
}: {
  validation: GameVariablesValidation;
  saving: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <Modal surface="tools"
      title="Conferma variabili validate"
      onClose={onClose}
      wide
      className="game-variable-validation-modal"
      footer={
        <>
          <button className="button secondary" type="button" onClick={onClose}>
            Torna alla modifica
          </button>
          <button
            className="button primary"
            type="button"
            disabled={saving || validation.changedCount === 0}
            onClick={onConfirm}
          >
            {saving ? "Salvataggio…" : "Conferma e salva nel database"}
          </button>
        </>
      }
    >
      <div className="game-variable-validation-summary">
        <span aria-hidden="true">✓</span>
        <div>
          <p className="eyebrow">Controllo server completato</p>
          <h3>{validation.message}</h3>
          <p>
            Formule, tipi, limiti e relazioni tra valori sono stati verificati.
            Il token di conferma scade dopo 15 minuti.
          </p>
        </div>
      </div>
      {validation.warnings.map((warning) => (
        <p className="game-variable-warning" key={warning}>{warning}</p>
      ))}
      {validation.changes.length ? (
        <div className="game-variable-change-list">
          {validation.changes.map((change) => (
            <article key={change.fieldId}>
              <strong>{change.label}</strong>
              <span><s>{change.before}</s><b aria-hidden="true">→</b><ins>{change.after}</ins></span>
            </article>
          ))}
        </div>
      ) : (
        <p className="game-variable-no-changes">
          Il profilo coincide già con i valori inseriti.
        </p>
      )}
      <p className="game-variable-refresh-note">
        I personaggi useranno le nuove regole al prossimo ricalcolo della scheda.
      </p>
    </Modal>
  );
}


export function GameVariablesPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["management", "game-variables"],
    queryFn: () =>
      getData<GameVariablesData>("/api/v1/management/game-variables"),
  });
  const [draft, setDraft] = useState<Draft>({});
  const [section, setSection] = useState<Section>("all");
  const [search, setSearch] = useState("");
  const [selectedFieldId, setSelectedFieldId] = useState("");
  const [validation, setValidation] =
    useState<GameVariablesValidation | null>(null);

  useEffect(() => {
    if (!query.data) return;
    setDraft(flatValues(query.data));
    setSelectedFieldId((current) =>
      current || query.data.groups[0]?.fields[0]?.id || ""
    );
  }, [query.data]);

  const fields = useMemo(
    () => query.data?.groups.flatMap((group) => group.fields) ?? [],
    [query.data],
  );
  const originals = useMemo(
    () => query.data ? flatValues(query.data) : {},
    [query.data],
  );
  const dirtyIds = useMemo(
    () => fields
      .filter((field) => !sameValue(draft[field.id], originals[field.id]))
      .map((field) => field.id),
    [draft, fields, originals],
  );
  const selectedField =
    fields.find((field) => field.id === selectedFieldId) || fields[0];
  const normalizedSearch = search.trim().toLocaleLowerCase("it");
  const visibleGroups = useMemo(
    () => (query.data?.groups ?? [])
      .filter((group) => section === "all" || group.section === section)
      .map((group) => ({
        ...group,
        fields: group.fields.filter((field) =>
          !normalizedSearch
          || `${field.label} ${field.key} ${field.group}`
            .toLocaleLowerCase("it")
            .includes(normalizedSearch)
        ),
      }))
      .filter((group) => group.fields.length),
    [normalizedSearch, query.data, section],
  );

  const validationMutation = useMutation({
    mutationFn: () =>
      command<{ management: { validation: GameVariablesValidation } }>(
        "management.variables.validate",
        { values: draft },
        "settings",
      ),
    onSuccess: (result) => {
      setValidation(result.data.management.validation);
      notify("Validazione completata. Controlla il riepilogo prima di salvare.");
    },
    onError: (error: ApiClientError) => {
      if (error.field) setSelectedFieldId(error.field);
      notify(error.message, "error");
    },
  });

  const saveMutation = useMutation({
    mutationFn: (previewToken: string) =>
      command<{ management: { variables: GameVariablesData } }>(
        "management.variables.save",
        { values: draft, previewToken },
        "settings",
      ),
    onSuccess: (result) => {
      queryClient.setQueryData(
        ["management", "game-variables"],
        result.data.management.variables,
      );
      setValidation(null);
      notify("Variabili di gioco salvate nel database.");
    },
    onError: (error: ApiClientError) => {
      setValidation(null);
      notify(error.message, "error");
    },
  });

  const updateValue = (fieldId: string, value: unknown) => {
    setDraft((current) => ({ ...current, [fieldId]: value }));
    setValidation(null);
  };

  if (query.isPending) {
    return <div className="page"><p>Caricamento variabili di gioco…</p></div>;
  }
  if (query.error || !query.data) {
    return (
      <div className="page">
        <section className="panel">
          <h1>Gestione Variabili</h1>
          <p>{(query.error as Error)?.message || "Profilo non disponibile."}</p>
        </section>
      </div>
    );
  }

  return (
    <div
      className="page game-variables-page"
      data-component-type="view"
      data-theme="arcane"
    >
      <header className="page-header">
        <div>
          <p className="eyebrow">Configurazione amministrativa</p>
          <h1>Gestione Variabili</h1>
          <p>
            Valori base, formule e regole globali del profilo
            {" "}<strong>{query.data.profile.name}</strong>.
          </p>
        </div>
        <div className="button-row">
          <Link className="button secondary" to="/tools/variables/damage">
            🛠️ Apri Tool Danno
          </Link>
          <Link className="button secondary" to="/tools">
            Tutti gli strumenti
          </Link>
          <button
            className="button primary"
            type="button"
            disabled={!dirtyIds.length || validationMutation.isPending}
            onClick={() => validationMutation.mutate()}
          >
            {validationMutation.isPending
              ? "Validazione…"
              : `Valida ${dirtyIds.length || ""} modifiche`}
          </button>
        </div>
      </header>

      <section
        className="game-variable-overview"
        data-component-type="panel"
        data-theme="gold"
      >
        <div>
          <span>Variabili gestite</span>
          <strong>{query.data.summary.fieldCount}</strong>
        </div>
        <div>
          <span>Valori base</span>
          <strong>{query.data.summary.baseCount}</strong>
        </div>
        <div>
          <span>Formule attive</span>
          <strong>{query.data.summary.formulaCount}</strong>
        </div>
        <div>
          <span>Regole globali</span>
          <strong>{query.data.summary.ruleCount}</strong>
        </div>
        <ol aria-label="Ordine di calcolo">
          {query.data.calculationOrder.map((step, index) => (
            <li key={step}><b>{index + 1}</b><span>{step}</span></li>
          ))}
        </ol>
      </section>

      <section
        className="game-variable-toolbar"
        data-component-type="toolbar"
        data-theme="dark"
      >
        <label>
          <span className="sr-only">Cerca variabile</span>
          <input
            type="search"
            value={search}
            placeholder="Cerca per nome o chiave tecnica…"
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <nav role="tablist" aria-label="Tipi di variabili">
          {query.data.sections.map((entry) => (
            <button
              key={entry.id}
              type="button"
              role="tab"
              aria-selected={section === entry.id}
              className={section === entry.id ? "active" : ""}
              onClick={() => setSection(entry.id)}
            >
              {entry.label}
            </button>
          ))}
        </nav>
        <span className={dirtyIds.length ? "dirty" : ""}>
          {dirtyIds.length
            ? `${dirtyIds.length} da validare`
            : "Profilo sincronizzato"}
        </span>
      </section>

      <div className="game-variable-layout">
        <main className="game-variable-groups">
          {visibleGroups.map((group) => (
            <section
              className="panel game-variable-group"
              data-component-type="panel"
              data-theme="default"
              key={group.id}
            >
              <header>
                <div>
                  <p className="eyebrow">{group.section}</p>
                  <h2>{group.label}</h2>
                </div>
                <span>{group.fields.length}</span>
              </header>
              <div>
                {group.fields.map((field) => {
                  const dirty = dirtyIds.includes(field.id);
                  return (
                    <article
                      className={`game-variable-field ${dirty ? "dirty" : ""}`}
                      data-component-type="field"
                      data-theme={dirty ? "gold" : "default"}
                      key={field.id}
                    >
                      <header>
                        <label htmlFor={`variable-${field.id}`}>
                          <strong>{field.label}</strong>
                          <code>{field.key}</code>
                        </label>
                        <button
                          type="button"
                          className={
                            selectedField?.id === field.id ? "active" : ""
                          }
                          onClick={() => setSelectedFieldId(field.id)}
                          aria-label={`Guida rapida: ${field.label}`}
                          title="Apri la guida rapida"
                        >
                          ?
                        </button>
                      </header>
                      <div id={`variable-${field.id}`}>
                        <VariableControl
                          field={field}
                          value={draft[field.id]}
                          onChange={(value) => updateValue(field.id, value)}
                        />
                      </div>
                      <footer>
                        <small>
                          Predefinito: {displayDefaultValue(field.defaultValue)}
                        </small>
                        {dirty && (
                          <button
                            type="button"
                            onClick={() =>
                              updateValue(field.id, originals[field.id])
                            }
                          >
                            Ripristina
                          </button>
                        )}
                      </footer>
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
          {!visibleGroups.length && (
            <section className="panel game-variable-empty">
              <span aria-hidden="true">⌕</span>
              <h2>Nessuna variabile trovata</h2>
              <p>Prova un termine più breve o cambia sezione.</p>
            </section>
          )}
        </main>

        <aside
          className="game-variable-guide"
          data-component-type="inspector"
          data-theme="arcane"
          aria-live="polite"
        >
          {selectedField ? (
            <>
              <header>
                <span aria-hidden="true">?</span>
                <div>
                  <p className="eyebrow">Guida rapida</p>
                  <h2>{selectedField.label}</h2>
                </div>
              </header>
              <section>
                <h3>Che cos’è</h3>
                <p>{selectedField.guide.summary}</p>
              </section>
              <section>
                <h3>Cosa influenza</h3>
                <p>{selectedField.guide.influence}</p>
              </section>
              <section className="game-variable-current-rule">
                <h3>Regola attiva</h3>
                <p>{selectedField.guide.currentRule}</p>
              </section>
              {selectedField.valueType === "formula" && (
                <section className="game-variable-formula-help">
                  <h3>Sintassi consentita</h3>
                  <p>
                    Usa <code>base.*</code>, <code>pre.*</code>,
                    {" "}<code>final.*</code> e <code>personaggio.*</code>.
                  </p>
                  <p>
                    Funzioni: <code>floor</code>, <code>ceil</code>,
                    {" "}<code>min</code>, <code>max</code>,
                    {" "}<code>abs</code>, <code>round</code>.
                  </p>
                </section>
              )}
              <footer>
                <small>Chiave tecnica</small>
                <code>{selectedField.guide.technicalKey}</code>
              </footer>
            </>
          ) : (
            <p>Scegli una variabile per leggere la guida.</p>
          )}
        </aside>
      </div>

      <footer className="game-variable-savebar">
        <div>
          <strong>
            {dirtyIds.length
              ? `${dirtyIds.length} modifiche non salvate`
              : "Nessuna modifica in sospeso"}
          </strong>
          <span>
            Il database non verrà modificato finché la validazione non sarà
            confermata.
          </span>
        </div>
        <button
          className="button secondary"
          type="button"
          disabled={!dirtyIds.length}
          onClick={() => {
            setDraft(originals);
            setValidation(null);
          }}
        >
          Annulla modifiche
        </button>
        <button
          className="button primary"
          type="button"
          disabled={!dirtyIds.length || validationMutation.isPending}
          onClick={() => validationMutation.mutate()}
        >
          Valida prima di salvare
        </button>
      </footer>

      {validation && (
        <ValidationReview
          validation={validation}
          saving={saveMutation.isPending}
          onClose={() => setValidation(null)}
          onConfirm={() =>
            saveMutation.mutate(validation.previewToken)
          }
        />
      )}
    </div>
  );
}
