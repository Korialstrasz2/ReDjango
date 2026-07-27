import { useEffect, useState, type ReactNode } from "react";

type EffectIconProps = {
  name?: string | null;
  assetUrl?: string | null;
  className?: string;
};

export function EffectIcon({ name, assetUrl = "", className = "" }: EffectIconProps) {
  const icon = (name || "runa").toLowerCase();
  const [assetUnavailable, setAssetUnavailable] = useState(false);
  useEffect(() => setAssetUnavailable(false), [assetUrl]);
  const paths: Record<string, ReactNode> = {
    fiamma: <path d="M13 3c1 4-2 5-2 8 0 1.7 1.3 3 3 3 2.2 0 3.8-2 3-5 2.6 2.2 4 4.9 4 7.4A8.5 8.5 0 0 1 4 16c0-3.7 2.2-7 6.3-10.2-.4 3.2.6 4.5 1.7 4.5C13.8 10.3 15.1 7.5 13 3Z" />,
    gelo: <path d="M12 2v20M4.2 6.5l15.6 11M4.2 17.5l15.6-11M9 4l3 2 3-2M9 20l3-2 3 2M4.8 10l.4 3.6-3 .6M21.8 9.8l-3 .6.4 3.6" />,
    fulmine: <path d="m13.5 2-8 12h6l-1 8 8-12h-6l1-8Z" />,
    scudo: <path d="M12 2.5 20 6v5.2c0 5-3.2 8.5-8 10.3-4.8-1.8-8-5.3-8-10.3V6l8-3.5Z" />,
    lama: <path d="m5 19 4-4m-2 6-4-4M10 14 20 4l1-2-2 1L9 13m1-5 6 6" />,
    cuore: <path d="M20.8 4.7a5.5 5.5 0 0 0-7.8 0L12 5.8l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.5a5.5 5.5 0 0 0 0-7.8Z" />,
    pozione: <path d="M9 2h6M10 2v5l-5 8.5A4.3 4.3 0 0 0 8.7 22h6.6a4.3 4.3 0 0 0 3.7-6.5L14 7V2M7.2 15h9.6" />,
    occhio: <><path d="M2 12s3.7-6 10-6 10 6 10 6-3.7 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
    vento: <path d="M3 8h10c3 0 3-4 0-4-1.2 0-2 .6-2.4 1.3M3 12h15c3 0 3 4 0 4-1.2 0-2-.6-2.4-1.3M3 16h7" />,
    luna: <path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5a9 9 0 1 0 12 12Z" />,
    teschio: <><path d="M5 10a7 7 0 1 1 14 0v4l-2 2v4H7v-4l-2-2v-4Z" /><circle cx="9" cy="11" r="1" /><circle cx="15" cy="11" r="1" /><path d="M10 16v4m4-4v4" /></>,
    runa: <path d="m12 2 7 5v10l-7 5-7-5V7l7-5Zm0 4v12M8 9l4 3 4-3M8 15l4-3 4 3" />,
    sole: <><circle cx="12" cy="12" r="4" /><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2" /></>,
    stella: <path d="m12 2.5 2.8 5.8 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.2l6.2-.9L12 2.5Z" />,
    corona: <path d="m3 7 5 4 4-7 4 7 5-4-2 12H5L3 7Zm3 15h12" />,
    libro: <path d="M3 5.5A3.5 3.5 0 0 1 6.5 2H11v18H6.5A3.5 3.5 0 0 0 3 23V5.5Zm18 0A3.5 3.5 0 0 0 17.5 2H13v18h4.5A3.5 3.5 0 0 1 21 23V5.5Z" />,
    pergamena: <path d="M7 3h11a3 3 0 0 1 0 6h-1v11H6a3 3 0 0 1 0-6h1V3Zm0 11h8M10 7h5m-5 4h5" />,
    chiave: <><circle cx="8" cy="15" r="4" /><path d="m11 12 9-9m-4 4 3 3m-6 0 3 3" /></>,
    catena: <path d="m9.5 14.5-2 2a3.5 3.5 0 0 1-5-5l3-3a3.5 3.5 0 0 1 5 0m4 1 2-2a3.5 3.5 0 0 1 5 5l-3 3a3.5 3.5 0 0 1-5 0M8 16l8-8" />,
    goccia: <path d="M12 2S5 10 5 15a7 7 0 0 0 14 0c0-5-7-13-7-13Z" />,
    foglia: <path d="M20.5 3.5C12 3 5 7 4 14c-.5 3.5 2 6 5 6 7 0 10.5-8 11.5-16.5ZM4 21c3-6 7-9 13-13" />,
    artiglio: <path d="M4 20c2-4 3-7 3-13m3 13c1-5 2-9 1-16m3 16c1-5 3-9 5-13M3 20h14" />,
    drago: <path d="M4 20c1-7 4-12 9-15l1-3 2 4 4 1-3 2c3 4 2 9-2 12-1-5-4-7-8-6m3-5-5-2 2 5" />,
    demone: <><path d="M5 8C3 5 4 3 4 3s4 1 5 4m10 1c2-3 1-5 1-5s-4 1-5 4" /><path d="M5 10a7 7 0 0 1 14 0v4a7 7 0 0 1-14 0v-4Zm4 2h.1m5.9 0h.1M9 17c2 1 4 1 6 0" /></>,
    spirito: <path d="M12 2c5 0 8 4 8 9v10l-4-3-4 3-4-3-4 3V11c0-5 3-9 8-9Zm-3 9h.1m5.9 0h.1" />,
    veleno: <><path d="M8 3h8l-1 4 4 4v8a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-8l4-4-1-4Z" /><path d="m9 13 6 5m0-5-6 5" /></>,
    barriera: <><path d="M12 2.5 20 6v5.2c0 5-3.2 8.5-8 10.3-4.8-1.8-8-5.3-8-10.3V6l8-3.5Z" /><path d="M8 12h8M12 8v8" /></>,
    tempo: <path d="M6 2h12M6 22h12M8 3c0 5 2 6 4 9-2 3-4 4-4 9m8-18c0 5-2 6-4 9 2 3 4 4 4 9M9 18h6" />,
    portale: <><ellipse cx="12" cy="12" rx="8" ry="10" /><ellipse cx="12" cy="12" rx="4" ry="6" /><path d="M12 6c2 3 2 9 0 12" /></>,
    musica: <path d="M9 18V5l10-2v13M9 9l10-2M6.5 22A2.5 2.5 0 1 0 6.5 17a2.5 2.5 0 0 0 0 5Zm10-2a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" />,
    silenzio: <><path d="M5 9h3l4-4v14l-4-4H5V9Z" /><path d="m17 9 5 5m0-5-5 5" /></>,
    invisibilita: <><path d="M2 12s3.7-6 10-6 10 6 10 6-3.7 6-10 6S2 12 2 12Z" /><path d="M4 20 20 4" /></>,
    paura: <><path d="M5 3h14v18H5z" /><circle cx="9" cy="10" r="1" /><circle cx="15" cy="10" r="1" /><path d="M9 17c1-3 5-3 6 0" /></>,
    sonno: <path d="M5 6h6l-6 6h6m2-8h6l-6 6h6M8 16h5l-5 5h5" />,
    rigenerazione: <><path d="M20 12a8 8 0 1 1-2.3-5.7L20 9" /><path d="M20 4v5h-5M12 8v8m-4-4h8" /></>,
    bilancia: <path d="M12 3v18M5 6h14M4 6 1 13h6L4 6Zm16 0-3 7h6l-3-7ZM8 21h8" />,
    pugno: <path d="M5 11V6a2 2 0 0 1 4 0v4-6a2 2 0 0 1 4 0v6-5a2 2 0 0 1 4 0v6-3a2 2 0 0 1 4 0v6c0 5-3 8-8 8-6 0-9-4-10-8l2-3Z" />,
    stivale: <path d="M8 2h8v11l5 4v4H4c-2 0-2-4 1-5l3-1V2Z" />,
    piuma: <path d="M20 3C12 3 5 9 5 17l-2 4m3-5c4 0 8-2 11-6m-8 2h7M8 8l4 2" />,
    bersaglio: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /><path d="m15 9 6-6m-4 0h4v4" /></>,
    maschera: <path d="M4 4c5 2 11 2 16 0v8c0 6-4 9-8 10-4-1-8-4-8-10V4Zm3 7 3 1m7-1-3 1m-5 5c2 1 4 1 6 0" />,
    cristallo: <path d="m12 2 7 7-7 13L5 9l7-7Zm-7 7h14M12 2v20M8 9l4 13 4-13" />,
    azione: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l4 2M3 12h3m12 0h3" /></>,
    spade: <path d="M5 20 19 3l2-1-1 2L7 21m12-1L5 3 3 2l1 2 13 17M3 17l4 4m14-4-4 4" />,
    armatura: <path d="M7 3 3 7l3 4v10h12V11l3-4-4-4-2 3H9L7 3Zm2 3v15m6-15v15" />,
    martello: <path d="m14 4 3-2 5 5-2 3-2-2L9 17l1 2-4 3-4-4 3-4 2 1 9-9-2-2Z" />,
    freccia: <path d="M3 21 21 3m-7 0h7v7M4 16l4 4m-1-7 4 4" />,
    armatura_rotta: <><path d="M7 3 3 7l3 4v10h12V11l3-4-4-4-2 3H9L7 3Z" /><path d="m13 6-3 6 4 2-3 7" /></>,
    zaino: <path d="M7 7V5a5 5 0 0 1 10 0v2m-9-4h8M5 7h14l2 14H3L5 7Zm3 4h8v5H8v-5Z" />,
    monete: <><circle cx="9" cy="13" r="6" /><circle cx="15" cy="10" r="6" /><path d="M13 7h4m-4 3h4m-4 3h3" /></>,
    vortice: <path d="M12 3c5 0 9 3 9 7s-4 7-9 7c-4 0-7-2-7-5s3-5 6-5c3 0 5 2 5 4s-2 3-4 3" />,
    scambio: <path d="M4 8h14l-3-3m3 3-3 3M20 16H6l3 3m-3-3 3-3" />,
    peso: <path d="M9 7a3 3 0 1 1 6 0h4l3 15H2L5 7h4Zm1 0h4" />,
    anello: <><circle cx="12" cy="14" r="7" /><path d="m8 8 2-5h4l2 5M10 3l2 5 2-5" /></>,
    orecchino: <path d="M9 4a3 3 0 1 1 3 3v6a4 4 0 1 0 4 4" />,
  };

  const aliases: Record<string, string> = {
    stanchezza: "tempo", modificatore_generale: "bilancia", fortuna: "stella", forza: "pugno",
    resistenza: "scudo", velocita: "stivale", agilita: "piuma", intelligenza: "libro",
    concentrazione: "bersaglio", personalita: "maschera", saggezza: "occhio", pf: "cuore",
    mana: "cristallo", energia: "sole", potere: "corona", pa: "azione", attacco: "spade",
    difesa: "scudo", rd_fis: "armatura", res_contundente: "martello", res_taglio: "lama",
    res_perforante: "freccia", res_fuoco: "fiamma", res_gelo: "gelo", res_elettro: "fulmine",
    rd_fuoco: "fiamma", rd_gelo: "gelo", rd_elettro: "fulmine", ap: "armatura_rotta",
    ap_percento: "bersaglio", slot_magici: "runa", slot_non_magici: "zaino",
    monete_per_slot: "monete", tier: "stella", sifone_di_mana: "vortice", en_per_mana: "scambio",
    pa_per_mana: "scambio", ogni_en_x_mana: "vortice", ogni_pa_x_mana: "vortice",
    sconto_mana_per_potere: "cristallo", sconto_pa_per_potere: "azione", mod_carico: "peso",
    mod_peso_equip: "piuma", orecchini_max: "orecchino", anelli_max: "anello", sacchi_max: "zaino",
    moltiplicatore_reagenti_rossi: "pozione", moltiplicatore_reagenti_verdi: "pozione",
    moltiplicatore_reagenti_blu: "pozione", moltiplicatore_reagenti_livello_1: "pozione",
    moltiplicatore_reagenti_livello_2: "pozione", moltiplicatore_reagenti_livello_3: "pozione",
    moltiplicatore_reagenti_livello_4: "pozione",
    atk_skill_taglio: "lama", atk_skill_contundente: "martello", atk_skill_perforante: "freccia",
    malattia: "veleno", benedizione: "stella", maledizione: "teschio", sangue: "goccia",
    luce: "sole", ombra: "luna",
  };
  const resolvedIcon = aliases[icon] || icon;

  return <span className={`effect-glyph ${className}`.trim()} aria-hidden="true">
    <svg
      className="effect-glyph-fallback"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >{paths[resolvedIcon] || paths.runa}</svg>
    {assetUrl && !assetUnavailable && <img
      className="effect-glyph-image"
      src={assetUrl}
      alt=""
      onError={() => setAssetUnavailable(true)}
    />}
  </span>;
}
