import torch.nn as nn


class MinimalLSTM(nn.Module):
    def __init__(self, n_feats: int, hidden_size: int, dropout: float):
        super().__init__()
        self.lstm = nn.LSTM(n_feats, hidden_size, batch_first=True)
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(self.drop(out[:, -1, :])).squeeze(-1)
