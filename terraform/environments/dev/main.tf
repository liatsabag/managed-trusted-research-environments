/**
 * Dev Environment Composition: Hub + 4 Spoke Research Rooms
 * GCP Health Data Platform POC
 */

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
  }
}

provider "google" {
  project = var.hub_project_id
  region  = var.region
}

provider "google-beta" {
  project = var.hub_project_id
  region  = var.region
}

# --------------------------------------------------------------------------------------------------
# 1. Central Management Hub Module
# --------------------------------------------------------------------------------------------------

module "hub" {
  source               = "../../hub"
  hub_project_id       = var.hub_project_id
  region               = var.region
  billing_project_id   = var.billing_project_id
  billing_dataset_id   = var.billing_dataset_id
  billing_export_table = var.billing_export_table
  admin_domain         = var.admin_domain
  deletion_protection  = var.deletion_protection
  enable_vpc_sc        = var.enable_vpc_sc
  access_policy_id     = var.access_policy_id
  ops_admin_members    = var.ops_admin_members
  tech_admin_members   = var.tech_admin_members
  dpo_members          = var.dpo_members
  environment          = var.environment
}

# --------------------------------------------------------------------------------------------------
# 2. Spoke Research Room: rr-oncology-01 (Immuno-Oncology Biomarker Study)
# --------------------------------------------------------------------------------------------------

module "room_oncology_01" {
  source                       = "../../modules/room"
  room_id                      = "rr-oncology-01"
  room_name                    = "Immuno-Oncology Biomarker Study"
  institute_id                 = "inst-mskcc"
  spoke_project_id             = "gcp-rr-spoke-oncology-01"
  hub_project_id               = var.hub_project_id
  region                       = var.region
  admin_domain                 = var.admin_domain
  deletion_protection          = var.deletion_protection
  enable_vpc_sc                = var.enable_vpc_sc
  access_policy_id             = var.access_policy_id
  hub_backend_sa_email         = module.hub.hub_backend_service_account_email
  shared_dataset_subscriptions = ["hub_shared_clinical", "hub_shared_reference"]

  researchers = [
    {
      researcher_id = "res-onc-01"
      first_name    = "Alice"
      last_name     = "Chen"
      primary_email = "dr.chen@${var.admin_domain}"
      role          = "Principal Investigator"
      access_state  = "ACTIVE"
    },
    {
      researcher_id = "res-onc-02"
      first_name    = "Marcus"
      last_name     = "Vance"
      primary_email = "dr.vance@${var.admin_domain}"
      role          = "Bioinformatician"
      access_state  = "ACTIVE"
    }
  ]
}

# --------------------------------------------------------------------------------------------------
# 3. Spoke Research Room: rr-genomics-02 (Rare Disease Whole-Genome Sequencing)
# --------------------------------------------------------------------------------------------------

module "room_genomics_02" {
  source                       = "../../modules/room"
  room_id                      = "rr-genomics-02"
  room_name                    = "Rare Disease Whole-Genome Sequencing"
  institute_id                 = "inst-broad"
  spoke_project_id             = "gcp-rr-spoke-genomics-02"
  hub_project_id               = var.hub_project_id
  region                       = var.region
  admin_domain                 = var.admin_domain
  deletion_protection          = var.deletion_protection
  enable_vpc_sc                = var.enable_vpc_sc
  access_policy_id             = var.access_policy_id
  hub_backend_sa_email         = module.hub.hub_backend_service_account_email
  shared_dataset_subscriptions = ["hub_shared_clinical", "hub_shared_reference"]

  researchers = [
    {
      researcher_id = "res-gen-01"
      first_name    = "Elena"
      last_name     = "Rostova"
      primary_email = "dr.rostova@${var.admin_domain}"
      role          = "Principal Investigator"
      access_state  = "ACTIVE"
    },
    {
      researcher_id = "res-gen-02"
      first_name    = "Daniel"
      last_name     = "Kim"
      primary_email = "dr.kim@${var.admin_domain}"
      role          = "Genomic Analyst"
      access_state  = "ACTIVE"
    }
  ]
}

# --------------------------------------------------------------------------------------------------
# 4. Spoke Research Room: rr-cardio-03 (Cardiovascular Risk Prediction Cohort)
# --------------------------------------------------------------------------------------------------

module "room_cardio_03" {
  source                       = "../../modules/room"
  room_id                      = "rr-cardio-03"
  room_name                    = "Cardiovascular Risk Prediction Cohort"
  institute_id                 = "inst-hopkins"
  spoke_project_id             = "gcp-rr-spoke-cardio-03"
  hub_project_id               = var.hub_project_id
  region                       = var.region
  admin_domain                 = var.admin_domain
  deletion_protection          = var.deletion_protection
  enable_vpc_sc                = var.enable_vpc_sc
  access_policy_id             = var.access_policy_id
  hub_backend_sa_email         = module.hub.hub_backend_service_account_email
  shared_dataset_subscriptions = ["hub_shared_clinical"]

  researchers = [
    {
      researcher_id = "res-car-01"
      first_name    = "Tariq"
      last_name     = "Al-Mansoor"
      primary_email = "dr.al-mansoor@${var.admin_domain}"
      role          = "Principal Investigator"
      access_state  = "ACTIVE"
    },
    {
      researcher_id = "res-car-02"
      first_name    = "Claire"
      last_name     = "Dupont"
      primary_email = "dr.dupont@${var.admin_domain}"
      role          = "Cardiologist"
      access_state  = "ACTIVE"
    }
  ]
}

# --------------------------------------------------------------------------------------------------
# 5. Spoke Research Room: rr-neurology-04 (Neurodegenerative Imaging & Clinical Trial)
# --------------------------------------------------------------------------------------------------

module "room_neurology_04" {
  source                       = "../../modules/room"
  room_id                      = "rr-neurology-04"
  room_name                    = "Neurodegenerative Imaging & Clinical Trial"
  institute_id                 = "inst-oxford"
  spoke_project_id             = "gcp-rr-spoke-neurology-04"
  hub_project_id               = var.hub_project_id
  region                       = var.region
  admin_domain                 = var.admin_domain
  deletion_protection          = var.deletion_protection
  enable_vpc_sc                = var.enable_vpc_sc
  access_policy_id             = var.access_policy_id
  hub_backend_sa_email         = module.hub.hub_backend_service_account_email
  shared_dataset_subscriptions = ["hub_shared_clinical", "hub_shared_reference"]

  researchers = [
    {
      researcher_id = "res-neu-01"
      first_name    = "Kenji"
      last_name     = "Takahashi"
      primary_email = "dr.takahashi@${var.admin_domain}"
      role          = "Principal Investigator"
      access_state  = "ACTIVE"
    },
    {
      researcher_id = "res-neu-02"
      first_name    = "Priya"
      last_name     = "Patel"
      primary_email = "dr.patel@${var.admin_domain}"
      role          = "Neurologist"
      access_state  = "ACTIVE"
    }
  ]
}
