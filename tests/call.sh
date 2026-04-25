#!/bin/bash

API_URL="https://voicekit-api.indusnettechnologies.com/api/call/outbound"
TOKEN="lvk_f00ut_adoBynDYlm5nOdV7c_lVp97Omw6vDLj1NJfyQ"

numbers=(
"+918697421450"
"+916002788139"
"+916291105616"
"+918910289513"
"+918777327374"
"+917595810513"
"+9187773115232"
)

for number in "${numbers[@]}"
do
  echo "Calling $number"

  curl --location "$API_URL" \
  --header "Content-Type: application/json" \
  --header "Authorization: Bearer $TOKEN" \
  --data "{
    \"user_id\":\"69a025c0909fa360aa2e8491\",
    \"assistant_id\":\"579ebc90-79e3-4ee8-ae69-8ee708c9ef53\",
    \"trunk_id\":\"69a02e89909fa360aa2e84f1\",
    \"to_number\":\"$number\"
  }"

  echo -e "\n----------------------\n"

done