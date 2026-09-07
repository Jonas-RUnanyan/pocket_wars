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
    {"Iosef Stalin", 25, 2, 12},  // Russia - Communism
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
    {"Edvard Beneš", 11, 1, 54},  // Czechoslovakia - Democracy
    {"Dimitrije Ljotić", 12, 0, 55},  // Yugoslavia - Fascism
    {"Milan Stojadinović", 12, 3, 56},  // Yugoslavia - Autocracy
    {"Peter II", 12, 3, 57},  // Yugoslavia - Autocracy
    {"Ljuba Davidović", 12, 1, 58},  // Yugoslavia - Democracy
    {"Josip Broz Tito", 12, 2, 59},  // Yugoslavia - Communism
    {"Zog I", 13, 3, 60},  // Albania - Autocracy
    {"Mehdi Frashëri", 13, 1, 61},  // Albania - Democracy
    {"Ali Kelmendi", 13, 2, 62},  // Albania - Communism
    {"Tefik Mborja", 13, 0, 63},  // Albania - Fascism
    {"Konstantinos Demertzis", 14, 1, 64},  // Greece - Democracy
    {"Ioannis Metaxás", 14, 3, 65},  // Greece - Autocracy
    {"Ioannis Metaxás", 14, 0, 66},  // Greece - Fascism
    {"George II", 14, 3, 67},  // Greece - Autocracy
    {"Nikos Zachariadis", 14, 2, 68},  // Greece - Communism
    {"Georgi Dimitrov", 15, 2, 69},  // Bulgaria - Communism
    {"Boris III", 15, 3, 70},  // Bulgaria - Autocracy
    {"Alexander Tsankov", 15, 0, 71},  // Bulgaria - Fascism
    {"Atanas Burov", 15, 1, 72},  // Bulgaria - Democracy
    {"Carol II", 16, 3, 73},  // Romania - Autocracy
    {"Boris Stefanov", 16, 2, 74},  // Romania - Communism
    {"Iuliu Maniu", 16, 1, 75},  // Romania - Democracy
    {"Corneliu Zelea Codreanu", 16, 0, 76},  // Romania - Fascism
    {"Ignacy Mościcki", 17, 3, 77},  // Poland - Autocracy
    {"Władysław Sikorski", 17, 1, 78},  // Poland - Democracy
    {"Bolesław Bierut", 17, 2, 79},  // Poland - Communism
    {"Bolesław Piasecki", 17, 0, 80},  // Poland - Fascism
    {"Antanas Smetona", 18, 3, 81},  // Lithuania - Autocracy
    {"Augustinas Voldemaras", 18, 0, 82},  // Lithuania - Fascism
    {"Antanas Sniečkus", 18, 2, 83},  // Lithuania - Communism
    {"Kazys Grinius", 18, 1, 84},  // Lithuania - Democracy
    {"Kārlis Ulmanis", 19, 3, 85},  // Latvia - Autocracy
    {"Brūno Kalniņš", 19, 1, 86},  // Latvia - Democracy
    {"Jānis Rudzutaks", 19, 2, 87},  // Latvia - Communism
    {"Gustavs Celmiņš", 19, 0, 88},  // Latvia - Fascism
    {"Konstantin Päts", 20, 3, 89},  // Estonia - Autocracy
    {"Andres Larka", 20, 0, 90},  // Estonia - Fascism
    {"Nigol Andresen", 20, 2, 91},  // Estonia - Communism
    {"Jaan Tõnisson", 20, 1, 92},  // Estonia - Democracy
    {"Thorvald Stauning", 21, 1, 93},  // Denmark - Democracy
    {"Frits Clausen", 21, 0, 94},  // Denmark - Fascism
    {"Aksel Larsen", 21, 2, 95},  // Denmark - Communism
    {"Christian X", 21, 3, 96},  // Denmark - Autocracy
    {"Gustaf V", 22, 3, 97},  // Sweden - Autocracy
    {"Sven Linderot", 22, 2, 98},  // Sweden - Communism
    {"Sven Olov Lindholm", 22, 0, 99},  // Sweden - Fascism
    {"Per Albin Hansson", 22, 1, 100},  // Sweden - Democracy
    {"Johan Nygaardsvold", 23, 1, 101},  // Norway - Democracy
    {"Vidkun Quisling", 23, 0, 102},  // Norway - Fascism
    {"Emil Løvlien", 23, 2, 103},  // Norway - Communism
    {"Haakon VII", 23, 3, 104},  // Norway - Autocracy
    {"Yrjö Sirola", 24, 2, 105},  // Finland - Communism
    {"Vilho Annala", 24, 0, 106},  // Finland - Fascism
    {"Carl Gustaf Emil Mannerheim", 24, 3, 107},  // Finland - Autocracy
    {"Pehr Evind Svinhufvud", 24, 1, 108},  // Finland - Democracy
    {"Konstantin Rodzaevsky", 25, 0, 109},  // Russia - Fascism
    {"Alexander Kerensky", 25, 1, 110},  // Russia - Democracy
    {"Pavel Milyukov", 25, 1, 111},  // Russia - Democracy
    {"Leon Trotsky", 25, 2, 112},  // Russia - Communism
    {"Kirill I ", 25, 3, 113},  // Russia - Autocracy
    {"Oswald Mosley", 26, 0, 114},  // United Kingdom - Fascism
    {"Harry Pollitt", 26, 2, 115},  // United Kingdom - Communism
    {"George V", 26, 3, 116},  // United Kingdom - Autocracy
    {"Edward VIII", 26, 3, 117},  // United Kingdom - Autocracy
    {"George VI", 26, 3, 118},  // United Kingdom - Autocracy
    {"Seán Murray", 27, 2, 119},  // Ireland - Communism
    {"Eoin O'Duffy", 27, 0, 120},  // Ireland - Fascism
    {"Éamon de Valera", 27, 1, 121},  // Ireland - Democracy
    {"Patrick Belton", 27, 3, 122},  // Ireland - Autocracy
    {"Mustafa Kemal Atatürk", 28, 3, 123},  // Turkey - Autocracy
    {"Recep Peker", 28, 0, 124},  // Turkey - Fascism
    {"Ali Fethi Okyar", 28, 1, 125},  // Turkey - Democracy
    {"Mustafa Kemal Atatürk", 28, 1, 126},  // Turkey - Democracy
    {"Şefik Hüsnü Deymer", 28, 2, 127},  // Turkey - Communism
    {"King Ghazi I", 29, 3, 128},  // Iraq - Autocracy
    {"Yasin al-Hashimi", 29, 3, 129},  // Iraq - Autocracy
    {"Yusuf Salman Yusuf", 29, 2, 130},  // Iraq - Communism
    {"Rashid Ali al-Gaylani", 29, 0, 131},  // Iraq - Fascism
    {"Kamil Chadirji", 29, 1, 132},  // Iraq - Democracy
    {"Abdulaziz Ibn Saud", 30, 3, 133},  // Saudi Arabia - Autocracy
    {"Sayyid Muhammad Tahir al-Dabbagh", 30, 1, 134},  // Saudi Arabia - Democracy
    {"Fuad Hamza", 30, 0, 135},  // Saudi Arabia - Fascism
    {"Reza Shah Pahlavi", 31, 3, 136},  // Persia - Autocracy
    {"Mohammad Mossadegh", 31, 1, 137},  // Persia - Democracy
    {"Abdul-Rahman Saif Azad", 31, 0, 138},  // Persia - Fascism
    {"Taqi Arani", 31, 2, 139}  // Persia - Communism
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
    {{40, 20, 20, 20}, 0, 50, {6, 34, 35, 36}},
    // Switzerland
    {{25, 25, 25, 25}, 3, 50, {38, 37, 39, LEADER_NONE}},
    // Italy
    {{25, 25, 25, 25}, 0, 50, {8, 41, 40, 42}},
    // Austria
    {{33, 25, 21, 21}, 0, 50, {43, 46, 44, 45}},
    // Hungary
    {{25, 25, 25, 25}, 3, 50, {48, 47, 49, 9}},
    // Czechoslovakia
    {{25, 25, 25, 25}, 1, 50, {51, 52, 50, LEADER_NONE}},
    // Yugoslavia
    {{25, 25, 25, 25}, 3, 50, {53, 56, 57, 54}},
    // Albania
    {{25, 25, 25, 25}, 3, 50, {61, 59, 60, 58}},
    // Greece
    {{25, 25, 25, 25}, 3, 50, {64, 62, 66, 63}},
    // Bulgaria
    {{25, 25, 25, 25}, 3, 50, {69, 70, 67, 68}},
    // Romania
    {{25, 25, 25, 25}, 3, 50, {74, 73, 72, 71}},
    // Poland
    {{25, 25, 25, 25}, 3, 50, {78, 76, 77, 75}},
    // Lithuania
    {{25, 25, 25, 25}, 3, 50, {80, 82, 81, 79}},
    // Latvia
    {{25, 25, 25, 25}, 3, 50, {86, 84, 85, 83}},
    // Estonia
    {{25, 25, 25, 25}, 3, 50, {88, 90, 89, 87}},
    // Denmark
    {{25, 25, 25, 25}, 1, 50, {92, 91, 93, 94}},
    // Sweden
    {{25, 25, 25, 25}, 1, 50, {97, 98, 96, 95}},
    // Norway
    {{25, 25, 25, 25}, 1, 50, {100, 99, 101, 102}},
    // Finland
    {{25, 25, 25, 25}, 1, 50, {104, 106, 103, 105}},
    // Russia
    {{0, 0, 100, 0}, 2, 50, {107, 108, 10, 111}},
    // United Kingdom
    {{25, 25, 25, 25}, 1, 50, {112, 11, 113, 114}},
    // Ireland
    {{25, 25, 25, 25}, 1, 50, {118, 119, 117, 120}},
    // Turkey
    {{25, 25, 25, 25}, 3, 50, {122, 124, 125, 121}},
    // Iraq
    {{25, 25, 25, 25}, 3, 50, {129, 130, 128, 127}},
    // Saudi Arabia
    {{25, 25, 25, 25}, 3, 50, {133, 132, LEADER_NONE, 131}},
    // Persia
    {{25, 25, 25, 25}, 3, 50, {136, 135, 137, 134}},
    // Austria-Hungary
    {{25, 25, 25, 25}, 3, 50, {LEADER_NONE, LEADER_NONE, LEADER_NONE, LEADER_NONE}}
};
