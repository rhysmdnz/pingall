{ check-jsonschema, runCommandNoCC, writeText, schemastore }:
{ name, content, schema ? "${schemastore}/src/schemas/json/${name}" }:
runCommandNoCC name {
  inherit schema;
  jsonUnvalidated = writeText "unvalidated-${name}" (builtins.toJSON content);
} ''${check-jsonschema}/bin/check-jsonschema --schemafile "$schema" "$jsonUnvalidated" && cp $jsonUnvalidated $out''
