"""Generation domain policies and services."""


from datetime import date, timedelta

from decimal import Decimal


import random


from app.domain.schema import _decimal


class RelationalGenerator:
    def generate(self, named, order, counts, seed):
        # ponytail: keep fixtures in memory up to 50,000 rows; stream batches for larger workloads.
        rng, records = random.Random(seed), {}
        for name in order:
            table, rows = named[name], []
            for index in range(counts[name]):
                row = {}
                for col in table["columns"]:
                    kind = col["type"]
                    if col["name"] == table["primary_key"]:
                        value = col["min"] + index
                    elif col.get("null_rate", 0) and rng.random() < col["null_rate"]:
                        value = None
                    elif col.get("references"):
                        target, key = col["references"].split(".")
                        value = rng.choice(records[target])[key]
                    elif kind == "integer":
                        value = rng.randint(col["min"], col["max"])
                    elif kind == "decimal":
                        scale = col["scale"]
                        units = rng.randint(int(_decimal(col["min"]) * 10 ** scale), int(_decimal(col["max"]) * 10 ** scale))
                        value = format(Decimal(units) / 10 ** scale, f".{scale}f")
                    elif kind == "enum":
                        value = rng.choices(col["values"], weights=col.get("weights"), k=1)[0]
                    else:
                        first, last = date.fromisoformat(col["min"]), date.fromisoformat(col["max"])
                        value = (first + timedelta(days=rng.randint(0, (last - first).days))).isoformat()
                    row[col["name"]] = value
                rows.append(row)
            records[name] = rows
        return records


_generate = RelationalGenerator().generate
