"""Inventario SOLO de slugs con sufijo .es reconocidos por OddsPapi."""
import os
from fuentes_es.catalogo import catalog_call
from fuentes_es.oddspapi import call, remaining_quota

def main():
    key=os.getenv("ODDS_PAPI_KEY","").strip()
    if not key:
        print("Sin clave, ninguna consulta.")
        return
    remaining=remaining_quota(call("account",{},key))
    if remaining<40:
        print("Cuota insuficiente; omitir catálogo.")
        return
    rows=catalog_call("bookmakers",key)
    if not isinstance(rows,list):
        raise ValueError("Formato inesperado del catálogo")
    es=sorted((r.get("slug",""),r.get("bookmakerName","")) for r in rows
              if isinstance(r,dict) and str(r.get("slug","")).endswith(".es"))
    print("Casas terminadas en .es:",len(es))
    for slug,name in es:print(slug,":",name)
    print("Advertencia: aparecer en el catálogo NO confirma cuotas en cada deporte/torneo.")
if __name__=="__main__":main()
