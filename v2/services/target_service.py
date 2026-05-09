"""Target discovery: curated library, UniProt search, RCSB PDB lookup."""
import json
import os
import concurrent.futures
import requests

from config.settings import (
    UNIPROT_SEARCH_URL, RCSB_SEARCH_URL, RCSB_DATA_URL, ALPHAFOLD_API_URL
)

_TARGETS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "curated_targets.json")
_TIMEOUT = 10


def get_curated_targets() -> list:
    with open(_TARGETS_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_curated_target(target_id: str) -> dict | None:
    for t in get_curated_targets():
        if t["id"] == target_id:
            return t
    return None


def search_uniprot(query: str, max_results: int = 8) -> list:
    """Search UniProt by gene name or protein name. Returns simplified cards."""
    try:
        params = {
            "query": f"{query} AND reviewed:true",
            "format": "json",
            "size": max_results,
            "fields": "accession,gene_names,protein_name,organism_name,length",
        }
        r = requests.get(UNIPROT_SEARCH_URL, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        results = r.json().get("results", [])
        cards = []
        for entry in results:
            acc = entry.get("primaryAccession", "")
            gene = ""
            if entry.get("genes"):
                gene = entry["genes"][0].get("geneName", {}).get("value", "")
            prot_name = ""
            if entry.get("proteinDescription"):
                prot_name = entry["proteinDescription"].get("recommendedName", {}).get("fullName", {}).get("value", "")
            org = entry.get("organism", {}).get("scientificName", "")
            cards.append({
                "uniprot_id": acc,
                "gene": gene,
                "protein_name": prot_name or gene,
                "organism": org,
                "length": entry.get("sequence", {}).get("length"),
                "source": "uniprot",
            })
        return cards
    except Exception as e:
        return [{"error": str(e)}]


def search_rcsb(uniprot_id: str, max_results: int = 5) -> list:
    """Find experimental PDB structures for a UniProt accession."""
    try:
        query = {
            "query": {
                "type": "terminal",
                "service": "text",
                "parameters": {
                    "attribute": "rcsb_polymer_entity_container_identifiers.uniprot_ids",
                    "operator": "in",
                    "value": [uniprot_id],
                },
            },
            "return_type": "entry",
            "request_options": {
                "sort": [{"sort_order": "asc", "attribute_name": "rcsb_entry_info.resolution_combined"}],
                "paginate": {"start": 0, "rows": max_results},
            },
        }
        r = requests.post(RCSB_SEARCH_URL, json=query, timeout=_TIMEOUT)
        r.raise_for_status()
        hits = r.json().get("result_set", [])
        pdb_ids = [h["identifier"] for h in hits]
        # Fetch metadata for first result
        cards = []
        for pid in pdb_ids:
            meta = _get_pdb_meta(pid)
            cards.append({
                "pdb_id": pid,
                "resolution": meta.get("resolution"),
                "method": meta.get("method"),
                "title": meta.get("title"),
                "release_date": meta.get("release_date"),
            })
        return cards
    except Exception:
        return []


def _get_pdb_meta(pdb_id: str) -> dict:
    try:
        r = requests.get(f"{RCSB_DATA_URL}/{pdb_id.upper()}", timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        info = data.get("rcsb_entry_info", {})
        res_list = info.get("resolution_combined", [])
        return {
            "resolution": res_list[0] if res_list else None,
            "method": info.get("experimental_method"),
            "title": data.get("struct", {}).get("title"),
            "release_date": data.get("rcsb_accession_info", {}).get("initial_release_date"),
        }
    except Exception:
        return {}


def check_alphafold(uniprot_id: str) -> dict | None:
    """Returns AlphaFold metadata including pdbUrl, or None if not available."""
    try:
        r = requests.get(f"{ALPHAFOLD_API_URL}/{uniprot_id}", timeout=_TIMEOUT)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        data = r.json()
        if data:
            return {
                "uniprot_id": uniprot_id,
                "entry_id": data[0].get("entryId"),
                "pdb_url": data[0].get("pdbUrl"),
                "cif_url": data[0].get("cifUrl"),
                "pae_image_url": data[0].get("paeImageUrl"),
                "version": data[0].get("latestVersion"),
                "source": "alphafold",
            }
        return None
    except Exception:
        return None


def full_target_search(query: str) -> dict:
    """
    Parallel search across curated targets + UniProt.
    Returns: {curated: [...], uniprot: [...]}
    """
    q_lower = query.lower()
    curated_hits = [
        t for t in get_curated_targets()
        if q_lower in t["name"].lower()
        or q_lower in t["disease"].lower()
        or q_lower in " ".join(t.get("tags", [])).lower()
        or q_lower in t["organism"].lower()
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        uni_future = ex.submit(search_uniprot, query)
        uniprot_hits = uni_future.result()

    return {"curated": curated_hits[:6], "uniprot": uniprot_hits[:6]}
