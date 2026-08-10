#include "political_data.h"

const Leader leaders[LEADER_COUNT] = {
    {"Niceto Alcalá-Zamora", 1, 1, 1},  // Spain - Democracy
    {"Emilio Mola", 1, 0, 2},  // Spain - Fascism
    {"Francisco Franco", 1, 0, 3},  // Spain - Fascism
    {"José Díaz", 1, 2, 4},  // Spain - Communism
    {"Juan de Borbón", 1, 3, 5},  // Spain - Autocracy
    {"Albert Lebrun", 2, 1, 6},  // France - Democracy
    {"Adolf Hitler", 6, 0, 7},  // Germany - Fascism
    {"Konrad Adenauer", 6, 1, 8},  // Germany - Democracy
    {"Benito Mussolini", 8, 0, 9},  // Italy - Fascism
    {"Miklos Horthy", 10, 3, 11},  // Hungary - Autocracy
    {"Iosef Stalin", 25, 2, 12},  // Soviet Union - Communism
    {"Stanley Baldwin", 26, 1, 13},  // United Kingdom - Democracy
    {"António de Oliveria Salazar", 0, 3, 14},  // Portugal - Autocracy
    {"Maurice Thorez", 2, 2, 15},  // France - Communism
    {"Napoleon VI", 2, 3, 16},  // France - Autocracy
    {"Jacques Doriot", 2, 0, 17},  // France - Fascism
    {"Bento Gonçalves", 0, 2, 18},  // Portugal - Communism
    {"Álvaro Cunhal", 0, 2, 19},  // Portugal - Communism
    {"António Sérgio", 0, 1, 20},  // Portugal - Democracy
    {"Francisco Rolão Preto", 0, 0, 21},  // Portugal - Fascism
    {"Joseph Bech", 3, 1, 22},  // Luxembourg - Democracy
    {"Pierre Dupong", 3, 1, 23},  // Luxembourg - Democracy
    {"Damian Kratzenberg", 3, 0, 24},  // Luxembourg - Fascism
    {"Dominique Urbany", 3, 2, 25},  // Luxembourg - Communism
    {"Charlotte", 3, 3, 26},  // Luxembourg - Autocracy
    {"Paul van Zeeland", 4, 1, 27},  // Belgium - Democracy
    {"Léon Degrelle", 4, 0, 28},  // Belgium - Fascism
    {"Joseph Jacquemotte", 4, 2, 29},  // Belgium - Communism
    {"Leopold III", 4, 3, 30},  // Belgium - Autocracy
    {"Hubert Pierlot", 4, 1, 31},  // Belgium - Democracy
    {"Wilhemina", 5, 3, 32},  // Netherlands - Autocracy
    {"Hendrikus Colijn", 5, 1, 33},  // Netherlands - Democracy
    {"Anton Mussert", 5, 0, 34},  // Netherlands - Fascism
    {"Louis de Visser", 5, 2, 35},  // Netherlands - Communism
    {"Toni Sender", 6, 1, 36},  // Germany - Democracy
    {"Ernst Thälmann", 6, 2, 37},  // Germany - Communism
    {"Wilhelm II", 6, 3, 38},  // Germany - Autocracy
    {"Swiss Federal Council", 7, 1, 39},  // Switzerland - Democracy
    {"Wilhelm Gustloff", 7, 0, 40},  // Switzerland - Fascism
    {"Léon Nicole", 7, 2, 41},  // Switzerland - Communism
    {"Palmiro Togliatti", 8, 2, 42},  // Italy - Communism
    {"Carlo Rosselli", 8, 1, 43},  // Italy - Democracy
    {"Vittorio Emanuele III", 8, 3, 44},  // Italy - Autocracy
    {"Kurt Schuschnigg", 9, 0, 45},  // Austria - Fascism
    {"Johann Koplenig", 9, 2, 46},  // Austria - Communism
    {"Otto von Habsburg", 9, 3, 47},  // Austria - Autocracy
    {"Otto Bauer", 9, 1, 48},  // Austria - Democracy
    {"Károly Peyer", 10, 1, 49},  // Hungary - Democracy
    {"Fidél Pálffy", 10, 0, 50},  // Hungary - Fascism
    {"Béla Kun", 10, 2, 51},  // Hungary - Communism
    {"Klement Gottwald", 11, 2, 52},  // Czechoslovakia - Communism
    {"Radola Gajda", 11, 0, 53},  // Czechoslovakia - Fascism
    {"Edvard Beneš", 11, 1, 54}  // Czechoslovakia - Democracy
};

const CountryPolitics country_politics[COUNTRY_POLITICS_COUNT] = {
    // Portugal
    {{40, 20, 20, 20}, 3, 73, {19, 18, 16, 12}},
    // Spain
    {{50, 35, 10, 5}, 1, 25, {1, 0, 3, 4}},
    // France
    {{8, 61, 23, 8}, 1, 50, {15, 5, 13, 14}},
    // Luxembourg
    {{25, 25, 25, 25}, 1, 50, {22, 20, 23, 24}},
    // Belgium
    {{25, 25, 25, 25}, 1, 50, {26, 25, 27, 28}},
    // Netherlands
    {{25, 25, 25, 25}, 1, 50, {32, 31, 33, 30}},
    // Germany
    {{40, 20, 20, 20}, 1, 50, {6, 34, 35, 36}},
    // Switzerland
    {{25, 25, 25, 25}, 3, 50, {38, 37, 39, LEADER_NONE}},
    // Italy
    {{25, 25, 25, 25}, 0, 50, {8, 41, 40, 42}},
    // Austria
    {{25, 25, 25, 25}, 3, 50, {43, 46, 44, 45}},
    // Hungary
    {{25, 25, 25, 25}, 3, 50, {48, 47, 49, 9}},
    // Czechoslovakia
    {{25, 25, 25, 25}, 3, 50, {51, 52, 50, LEADER_NONE}},
    // Yugoslavia
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Albania
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Greece
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Bulgaria
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Romania
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Poland
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Lithuania
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Latvia
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Estonia
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Denmark
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Sweden
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Norway
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Finland
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Soviet Union
    {{0, 0, 100, 0}, 2, 50, {LEADER_NONE, LEADER_NONE, 10, LEADER_NONE}},
    // United Kingdom
    {{25, 25, 25, 25}, 1, 50, {LEADER_NONE, 11, LEADER_NONE, LEADER_NONE}},
    // Ireland
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Turkey
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Iraq
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Saudi Arabia
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}},
    // Persia
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}}
};
