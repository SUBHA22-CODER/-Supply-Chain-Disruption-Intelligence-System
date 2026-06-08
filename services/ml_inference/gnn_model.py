"""
Task 06: GraphSAGE model for supply chain disruption prediction.

Heterogeneous graph with Supplier and SKU nodes, SUPPLIES and DEPENDS_ON edges.
3-layer GraphSAGE with mean aggregation, focal loss, temporal graph snapshots.
Evaluated with F1 and AUC-PR. Logged to MLflow.
"""
import os
import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau
from sklearn.metrics import (
    f1_score, precision_recall_curve, auc, confusion_matrix,
    classification_report,
)
from datetime import datetime, timedelta

try:
    import mlflow
    import mlflow.pytorch
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False


# ── Focal Loss ──────────────────────────────────────────────────────────────
class FocalLoss(nn.Module):
    def __init__(self, gamma: float = 2.0, alpha: float = 0.25):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce = F.binary_cross_entropy_with_logits(inputs, targets, reduction="none")
        pt = torch.exp(-bce)
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        loss = alpha_t * ((1 - pt) ** self.gamma) * bce
        return loss.mean()


# ── GraphSAGE Layer ─────────────────────────────────────────────────────────
class SAGELayer(nn.Module):
    """Single GraphSAGE layer with mean aggregation."""
    def __init__(self, in_dim: int, out_dim: int, dropout: float = 0.3):
        super().__init__()
        self.linear = nn.Linear(in_dim * 2, out_dim)
        self.bn = nn.BatchNorm1d(out_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        # Mean aggregation of neighbours
        deg = adj.sum(dim=1, keepdim=True).clamp(min=1)
        neigh_agg = torch.mm(adj, x) / deg
        combined = torch.cat([x, neigh_agg], dim=1)
        out = self.linear(combined)
        if out.size(0) > 1:
            out = self.bn(out)
        out = F.relu(out)
        out = self.dropout(out)
        return out


# ── GraphSAGE Model ─────────────────────────────────────────────────────────
class GraphSAGEDisruption(nn.Module):
    """3-layer GraphSAGE for binary disruption prediction per supplier node."""
    def __init__(self, supplier_feat_dim: int = 6, sku_feat_dim: int = 3,
                 hidden_dim: int = 128, dropout: float = 0.3):
        super().__init__()
        # Project different node types into same dim
        self.supplier_proj = nn.Linear(supplier_feat_dim, hidden_dim)
        self.sku_proj = nn.Linear(sku_feat_dim, hidden_dim)

        self.sage1 = SAGELayer(hidden_dim, hidden_dim, dropout)
        self.sage2 = SAGELayer(hidden_dim, hidden_dim, dropout)
        self.sage3 = SAGELayer(hidden_dim, hidden_dim, dropout)

        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

    def forward(self, supplier_x: torch.Tensor, sku_x: torch.Tensor,
                adj: torch.Tensor, num_suppliers: int) -> torch.Tensor:
        # Project to shared space
        s_emb = F.relu(self.supplier_proj(supplier_x))
        k_emb = F.relu(self.sku_proj(sku_x))
        x = torch.cat([s_emb, k_emb], dim=0)

        # 3 SAGE layers
        x = self.sage1(x, adj)
        x = self.sage2(x, adj)
        x = self.sage3(x, adj)

        # Only classify supplier nodes
        supplier_emb = x[:num_suppliers]
        logits = self.classifier(supplier_emb).squeeze(-1)
        return logits, supplier_emb


# ── Graph Construction from Dataset ─────────────────────────────────────────
def build_snapshot_graph(df_snapshot: pd.DataFrame, supplier_ids: list,
                         num_skus: int = 30):
    """Build a graph snapshot from a single week of data.

    Returns supplier features, SKU features, adjacency matrix, and labels.
    """
    num_suppliers = len(supplier_ids)
    total_nodes = num_suppliers + num_skus

    # Supplier features: aggregate the week's daily features per supplier
    feat_cols = ["weather_severity", "geopolitical_risk", "port_congestion",
                 "financial_stress", "news_sentiment", "lead_time_variance"]
    supplier_feats = np.zeros((num_suppliers, len(feat_cols)), dtype=np.float32)
    labels = np.zeros(num_suppliers, dtype=np.float32)

    for i, sid in enumerate(supplier_ids):
        sub = df_snapshot[df_snapshot["supplier_id"] == sid]
        if len(sub) > 0:
            supplier_feats[i] = sub[feat_cols].mean().values.astype(np.float32)
            labels[i] = float(sub["disruption_occurred"].max())

    # SKU features: synthetic (demand_volatility, criticality, stock_level)
    np.random.seed(hash(str(df_snapshot["date"].iloc[0])) % 2**31 if len(df_snapshot) > 0 else 0)
    sku_feats = np.random.rand(num_skus, 3).astype(np.float32)

    # Adjacency: SUPPLIES edges (supplier -> SKU) + DEPENDS_ON (supplier -> supplier)
    adj = np.zeros((total_nodes, total_nodes), dtype=np.float32)

    # SUPPLIES: each supplier supplies 1-3 random SKUs
    for i in range(num_suppliers):
        n_skus = np.random.randint(1, min(4, num_skus + 1))
        sku_indices = np.random.choice(num_skus, size=n_skus, replace=False)
        for sk in sku_indices:
            adj[i, num_suppliers + sk] = 1.0
            adj[num_suppliers + sk, i] = 1.0  # undirected for message passing

    # DEPENDS_ON: tier-3 -> tier-2 -> tier-1
    tiers = df_snapshot.groupby("supplier_id")["tier"].first().to_dict()
    tier_map = {sid: tiers.get(sid, 3) for sid in supplier_ids}
    for i, sid in enumerate(supplier_ids):
        if tier_map[sid] == 3:
            t2_candidates = [j for j, s in enumerate(supplier_ids) if tier_map[s] == 2]
            if t2_candidates:
                dep = np.random.choice(t2_candidates)
                adj[i, dep] = 1.0
                adj[dep, i] = 1.0
        elif tier_map[sid] == 2:
            t1_candidates = [j for j, s in enumerate(supplier_ids) if tier_map[s] == 1]
            if t1_candidates:
                dep = np.random.choice(t1_candidates)
                adj[i, dep] = 1.0
                adj[dep, i] = 1.0

    return (
        torch.tensor(supplier_feats),
        torch.tensor(sku_feats),
        torch.tensor(adj),
        torch.tensor(labels),
    )


def create_weekly_snapshots(df: pd.DataFrame, supplier_ids: list):
    """Split dataframe into weekly temporal snapshots."""
    df = df.copy()
    df["week"] = df["date"].dt.isocalendar().week.astype(int) + \
                 (df["date"].dt.year - df["date"].dt.year.min()) * 52
    weeks = sorted(df["week"].unique())
    snapshots = []
    for w in weeks:
        week_df = df[df["week"] == w]
        snapshots.append(build_snapshot_graph(week_df, supplier_ids))
    return snapshots


# ── Training Loop ───────────────────────────────────────────────────────────
def train_gnn(data_path: str = None):
    """Full training pipeline."""
    if data_path is None:
        data_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "processed", "disruption_dataset.parquet"
        )

    print("Loading dataset...")
    df = pd.read_parquet(data_path)
    df["date"] = pd.to_datetime(df["date"])
    supplier_ids = sorted(df["supplier_id"].unique().tolist())

    # Split by temporal partition
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "val"]
    test_df = df[df["split"] == "test"]

    print("Creating weekly snapshots...")
    train_snaps = create_weekly_snapshots(train_df, supplier_ids)
    val_snaps = create_weekly_snapshots(val_df, supplier_ids)
    test_snaps = create_weekly_snapshots(test_df, supplier_ids)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = GraphSAGEDisruption(
        supplier_feat_dim=6, sku_feat_dim=3,
        hidden_dim=128, dropout=0.3,
    ).to(device)

    optimizer = Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = FocalLoss(gamma=2.0, alpha=0.25)

    num_suppliers = len(supplier_ids)
    best_f1 = 0.0
    patience_counter = 0
    patience_limit = 10
    epochs = 100

    if HAS_MLFLOW:
        mlflow.set_experiment("supply_chain_gnn")
        mlflow.start_run(run_name="graphsage_disruption")
        mlflow.log_params({
            "hidden_dim": 128, "dropout": 0.3, "lr": 1e-3,
            "weight_decay": 1e-4, "gamma": 2.0, "alpha": 0.25,
            "epochs": epochs, "patience": patience_limit,
        })

    print(f"Training on {device} for {epochs} epochs...")
    for epoch in range(epochs):
        model.train()
        epoch_loss = 0.0
        for s_feat, k_feat, adj, labels in train_snaps:
            s_feat, k_feat, adj, labels = (
                s_feat.to(device), k_feat.to(device), adj.to(device), labels.to(device)
            )
            optimizer.zero_grad()
            logits, _ = model(s_feat, k_feat, adj, num_suppliers)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()

        avg_loss = epoch_loss / max(len(train_snaps), 1)

        # Validation
        model.eval()
        all_preds, all_labels, all_val_probs = [], [], []
        with torch.no_grad():
            for s_feat, k_feat, adj, labels in val_snaps:
                s_feat, k_feat, adj, labels = (
                    s_feat.to(device), k_feat.to(device), adj.to(device), labels.to(device)
                )
                logits, _ = model(s_feat, k_feat, adj, num_suppliers)
                probs = torch.sigmoid(logits)
                preds = (probs > 0.5).float()
                all_preds.extend(preds.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
                all_val_probs.extend(probs.cpu().numpy())

        val_f1 = f1_score(all_labels, all_preds, zero_division=0)
        prec, rec, _ = precision_recall_curve(all_labels, all_val_probs)
        val_auc_pr = auc(rec, prec) if len(set(all_labels)) > 1 else 0.0
        scheduler.step(avg_loss)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d} | Loss {avg_loss:.4f} | Val F1 {val_f1:.4f} | Val AUC-PR {val_auc_pr:.4f}")

        if HAS_MLFLOW:
            mlflow.log_metrics({"train_loss": avg_loss, "val_f1": val_f1, "val_auc_pr": val_auc_pr}, step=epoch)

        if val_f1 > best_f1:
            best_f1 = val_f1
            patience_counter = 0
            model_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "models"
            )
            os.makedirs(model_dir, exist_ok=True)
            torch.save(model.state_dict(), os.path.join(model_dir, "gnn_best.pt"))
        else:
            patience_counter += 1
            if patience_counter >= patience_limit:
                print(f"  Early stopping at epoch {epoch+1}")
                break

    # ── Test Evaluation ──
    print("\n--- Test Evaluation ---")
    model.load_state_dict(torch.load(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                     "data", "models", "gnn_best.pt"),
        weights_only=True,
    ))
    model.eval()
    all_preds, all_labels, all_probs = [], [], []
    with torch.no_grad():
        for s_feat, k_feat, adj, labels in test_snaps:
            s_feat, k_feat, adj, labels = (
                s_feat.to(device), k_feat.to(device), adj.to(device), labels.to(device)
            )
            logits, _ = model(s_feat, k_feat, adj, num_suppliers)
            probs = torch.sigmoid(logits)
            preds = (probs > 0.5).float()
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())

    test_f1 = f1_score(all_labels, all_preds, zero_division=0)
    prec, rec, _ = precision_recall_curve(all_labels, all_probs)
    test_auc_pr = auc(rec, prec) if len(set(all_labels)) > 1 else 0.0

    print(f"  Test F1:     {test_f1:.4f}")
    print(f"  Test AUC-PR: {test_auc_pr:.4f}")
    print(f"\n  Confusion Matrix:\n{confusion_matrix(all_labels, all_preds)}")
    print(f"\n{classification_report(all_labels, all_preds, zero_division=0)}")

    if HAS_MLFLOW:
        mlflow.log_metrics({"test_f1": test_f1, "test_auc_pr": test_auc_pr})
        mlflow.pytorch.log_model(model, "graphsage_model")
        mlflow.end_run()

    return model


if __name__ == "__main__":
    train_gnn()
