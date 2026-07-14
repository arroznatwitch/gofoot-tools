// Definição das ligas: País -> Liga -> lista de clubes (o nome do clube tem de
// bater com a coluna "Club" do players.csv). Editável à mão.
//
// Carregado por <script> (e não por fetch de .json) para funcionar mesmo quando
// abres o index.html directamente por duplo-clique (file://), onde o fetch de
// ficheiros locais é bloqueado pelo browser.
window.LEAGUES_DATA = {
    "Brasil": {
        "Liga Brasileira 26/27": [
            "SPO", "AFC", "VIT", "COR", "SAN", "SEP", "JUV", "CRI", "ATP", "FIG",
            "ITU", "CHA", "CEC", "BRA", "ATM", "FOR", "SPT", "INT", "FLU", "Vasco Da Gama"
        ]
    },
    "Portugal": {
        "Liga Portuguesa 26/27": [
            "FC Porto", "Benfica", "Sporting CP", "BRG", "VTSC", "Santa Clara",
            "Gil Vicente", "Famalicão", "Marítimo", "Estoril Praia", "Rio Ave",
            "Alverca SAD", "Casa Pia", "Arouca", "Moreirense", "Nacional da Madeira",
            "Académico de Viseu", "Estrela da Amadora SAD"
        ]
    },
    "Jamaica": {
        "Liga da Jamaica 26/27": [
            "Harbour View", "Chapelton Maroons", "Arnett Gardens", "Portmore Utd",
            "Cavalier", "Dunbeholden", "Mount Pleasant FC", "Tivoli Gardens",
            "Racing Utd (JAM)", "Montego Bay Utd", "Treasure Beach", "Waterhouse",
            "Molynes Utd", "Spanish Town Police"
        ]
    }
};
